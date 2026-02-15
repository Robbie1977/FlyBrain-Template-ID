const express = require('express');
const { exec, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// Shell-escape: wrap in single quotes, escape embedded single quotes.
// Single-quoting is the strongest bash quoting — everything inside is literal
// (no variable expansion, no subshell syntax, no globbing).
function shellEscape(str) {
    return "'" + str.replace(/'/g, "'\\''") + "'";
}

const app = express();
const PORT = 3000;
const ORIENTATIONS_FILE = path.join(__dirname, 'orientations.json');

// Middleware
app.use(express.json());
app.use(express.static('public'));

// Alignment queue
let alignmentQueue = [];
let currentAlignment = null;
let alignmentStatus = {}; // image_base -> { status: 'preparing|queued|processing|completed|failed', progress: 0-100, error: '' }
let preparingImages = new Set(); // Track images currently being prepared (NRRD/channel creation)

function readOrientations() {
    if (fs.existsSync(ORIENTATIONS_FILE)) {
        return JSON.parse(fs.readFileSync(ORIENTATIONS_FILE, 'utf8'));
    }
    return {};
}

function writeOrientations(data) {
    fs.writeFileSync(ORIENTATIONS_FILE, JSON.stringify(data, null, 2));
}

// --- Persistent alignment state ---
const ALIGNMENT_STATE_FILE = path.join(__dirname, 'alignment_progress.json');

const STAGE_PROGRESS = {
    'initializing': 0,
    'set_lps': 2,
    'initial_affine': 5,
    'affine_registration': 10,
    'warp': 40,
    'reformat_signal': 75,
    'reformat_background': 85,
    'thumbnails': 95,
    'completed': 100
};

const STAGE_LABELS = {
    'initializing': 'Initializing',
    'set_lps': 'Setting LPS orientation',
    'initial_affine': 'Initial affine transform',
    'affine_registration': 'Affine registration',
    'warp': 'Non-linear warping',
    'reformat_signal': 'Reformatting signal',
    'reformat_background': 'Reformatting background',
    'thumbnails': 'Generating thumbnails',
    'completed': 'Completed'
};

function readAlignmentState() {
    try {
        if (fs.existsSync(ALIGNMENT_STATE_FILE)) {
            return JSON.parse(fs.readFileSync(ALIGNMENT_STATE_FILE, 'utf8'));
        }
    } catch (e) {
        console.error('Failed to read alignment state:', e.message);
    }
    return { queue: [], jobs: {} };
}

function writeAlignmentState() {
    const state = { queue: alignmentQueue, jobs: alignmentStatus };
    try {
        const tmp = ALIGNMENT_STATE_FILE + '.tmp';
        fs.writeFileSync(tmp, JSON.stringify(state, null, 2));
        fs.renameSync(tmp, ALIGNMENT_STATE_FILE);
    } catch (e) {
        console.error('Failed to write alignment state:', e.message);
    }
}

function loadPersistedState() {
    const state = readAlignmentState();
    alignmentQueue = state.queue || [];
    alignmentStatus = state.jobs || {};
    // Mark 'processing' jobs as 'interrupted' — they'll be re-detected or re-queued
    for (const key of Object.keys(alignmentStatus)) {
        if (alignmentStatus[key].status === 'processing') {
            alignmentStatus[key].status = 'interrupted';
        }
    }
    currentAlignment = null;
    console.log(`Loaded persisted state: ${Object.keys(alignmentStatus).length} jobs, ${alignmentQueue.length} queued`);

    // Recover completed alignments from corrected/ directory files
    // This handles the case where alignment_progress.json was lost (e.g., container restart
    // before the fix to store it on a mounted volume)
    recoverCompletedAlignments();
}

function recoverCompletedAlignments() {
    const correctedDir = path.join(__dirname, 'corrected');
    if (!fs.existsSync(correctedDir)) return;

    let recovered = 0;
    try {
        const files = fs.readdirSync(correctedDir);
        // Find per-job progress files: {imageBase}_alignment_progress.json
        const progressFiles = files.filter(f => f.endsWith('_alignment_progress.json'));

        for (const pf of progressFiles) {
            const imageBase = pf.replace('_alignment_progress.json', '');

            // Skip if we already have state for this job
            if (alignmentStatus[imageBase]) continue;

            try {
                const progress = JSON.parse(fs.readFileSync(path.join(correctedDir, pf), 'utf8'));

                // Check if alignment actually completed
                if (progress.current_stage === 'completed' || progress.completed_at) {
                    alignmentStatus[imageBase] = {
                        status: 'completed',
                        progress: 100,
                        current_stage: 'completed',
                        stages: progress.stages || {},
                        error: '',
                        queued_at: progress.started_at || '',
                        started_at: progress.started_at || '',
                        completed_at: progress.completed_at || ''
                    };
                    recovered++;
                    console.log(`  Recovered completed alignment: ${imageBase}`);
                } else if (progress.error || progress.failed_at) {
                    alignmentStatus[imageBase] = {
                        status: 'failed',
                        progress: 0,
                        current_stage: progress.current_stage || 'unknown',
                        stages: progress.stages || {},
                        error: progress.error || 'Unknown error (recovered from disk)',
                        queued_at: progress.started_at || '',
                        started_at: progress.started_at || '',
                        completed_at: progress.failed_at || ''
                    };
                    recovered++;
                    console.log(`  Recovered failed alignment: ${imageBase}`);
                }
            } catch (e) {
                // Corrupted progress file, skip
            }
        }

        if (recovered > 0) {
            console.log(`Recovered ${recovered} alignment(s) from corrected/ directory`);
            writeAlignmentState();
        }
    } catch (e) {
        console.error('Error during alignment recovery:', e.message);
    }
}

function getJobStageProgress(imageBase) {
    // First try the per-job progress file written by align_single_cmtk.sh
    const progressFile = path.join(__dirname, 'corrected', `${imageBase}_alignment_progress.json`);
    try {
        if (fs.existsSync(progressFile)) {
            return JSON.parse(fs.readFileSync(progressFile, 'utf8'));
        }
    } catch (e) {}

    // Fallback: infer stage from filesystem state
    return inferStageFromFiles(imageBase);
}

function inferStageFromFiles(imageBase) {
    const xformDir = path.join(__dirname, 'corrected', `${imageBase}_xform`);
    const signalAligned = path.join(__dirname, 'corrected', `${imageBase}_signal_aligned.nrrd`);
    const bgAligned = path.join(__dirname, 'corrected', `${imageBase}_background_aligned.nrrd`);
    const thumbnails = path.join(__dirname, 'corrected', `${imageBase}_alignment_thumbnails.json`);

    if (fs.existsSync(thumbnails)) {
        return { current_stage: 'completed', stages: {} };
    }
    if (fs.existsSync(signalAligned) && fs.existsSync(bgAligned)) {
        return { current_stage: 'thumbnails', stages: {} };
    }
    if (fs.existsSync(signalAligned)) {
        return { current_stage: 'reformat_background', stages: {} };
    }

    if (!fs.existsSync(xformDir)) return null;

    const warpXform = path.join(xformDir, 'warp.xform');
    const affineXform = path.join(xformDir, 'affine.xform');
    const initialXform = path.join(xformDir, 'initial.xform');

    if (fs.existsSync(warpXform)) {
        return { current_stage: 'reformat_signal', stages: {} };
    }
    if (fs.existsSync(affineXform)) {
        return { current_stage: 'warp', stages: {} };
    }
    if (fs.existsSync(initialXform)) {
        return { current_stage: 'affine_registration', stages: {} };
    }

    return { current_stage: 'initial_affine', stages: {} };
}

// Detect existing alignment processes from previous server sessions
function detectRunningAlignments() {
    exec('ps aux | grep -E "CMTK/bin/(registration|warp|reformatx|make_initial_affine)|align_single_cmtk\\.sh" | grep -v grep', (error, stdout) => {
        if (error || !stdout.trim()) {
            console.log('No existing alignment processes detected');
            requeueInterruptedJobs();
            return;
        }

        const lines = stdout.trim().split('\n');
        const runningImages = new Set();

        for (const line of lines) {
            // Match align_single_cmtk.sh wrapper
            let match = line.match(/align_single_cmtk\.sh\s+"?([^"\s]+)"?/);
            if (match) { runningImages.add(match[1].trim()); continue; }
            // Match CMTK binary - extract image base from xform directory path
            match = line.match(/corrected\/(.+?)_xform\//);
            if (match) { runningImages.add(match[1].trim()); continue; }
            // Match from channel file path
            match = line.match(/channels\/(.+?)_(?:background|signal)\.nrrd/);
            if (match) { runningImages.add(match[1].trim()); }
        }

        if (runningImages.size === 0) {
            console.log('No existing alignment processes detected');
            requeueInterruptedJobs();
            return;
        }

        for (const imageBase of runningImages) {
            console.log(`Detected running alignment for: ${imageBase}`);
            alignmentStatus[imageBase] = {
                status: 'processing',
                progress: 0,
                error: '',
                queued_at: alignmentStatus[imageBase]?.queued_at || new Date().toISOString()
            };
            // Remove from queue if present
            const idx = alignmentQueue.indexOf(imageBase);
            if (idx > -1) alignmentQueue.splice(idx, 1);
        }

        // Set the first as current
        currentAlignment = runningImages.values().next().value;
        writeAlignmentState();

        // Monitor these processes
        monitorExistingAlignments(runningImages);

        // Re-queue any remaining interrupted jobs
        requeueInterruptedJobs();
    });
}

function requeueInterruptedJobs() {
    let changed = false;
    for (const [imageBase, job] of Object.entries(alignmentStatus)) {
        if (job.status === 'interrupted') {
            console.log(`Re-queuing interrupted job: ${imageBase}`);
            job.status = 'queued';
            if (!alignmentQueue.includes(imageBase)) {
                alignmentQueue.push(imageBase);
            }
            changed = true;
        }
    }
    if (changed) writeAlignmentState();
    processAlignmentQueue();
}

function monitorExistingAlignments(imageSet) {
    const checkInterval = setInterval(() => {
        exec('ps aux | grep -E "CMTK/bin/(registration|warp|reformatx|make_initial_affine)|align_single_cmtk\\.sh" | grep -v grep', (error, stdout) => {
            const stillRunning = new Set();
            if (!error && stdout.trim()) {
                const lines = stdout.trim().split('\n');
                for (const line of lines) {
                    let match = line.match(/align_single_cmtk\.sh\s+"?([^"\s]+)"?/);
                    if (match) { stillRunning.add(match[1].trim()); continue; }
                    match = line.match(/corrected\/(.+?)_xform\//);
                    if (match) { stillRunning.add(match[1].trim()); continue; }
                    match = line.match(/channels\/(.+?)_(?:background|signal)\.nrrd/);
                    if (match) { stillRunning.add(match[1].trim()); }
                }
            }

            // Update progress for still-running jobs from per-job files
            for (const imageBase of imageSet) {
                if (stillRunning.has(imageBase) && alignmentStatus[imageBase]) {
                    const stageProgress = getJobStageProgress(imageBase);
                    if (stageProgress) {
                        const stage = stageProgress.current_stage || 'initializing';
                        alignmentStatus[imageBase].progress = STAGE_PROGRESS[stage] || 0;
                        alignmentStatus[imageBase].current_stage = stage;
                        alignmentStatus[imageBase].stages = stageProgress.stages;
                        alignmentStatus[imageBase].started_at = stageProgress.started_at || alignmentStatus[imageBase].started_at;
                    }
                }
            }

            // Check for any that finished
            for (const imageBase of imageSet) {
                if (!stillRunning.has(imageBase) && alignmentStatus[imageBase]?.status === 'processing') {
                    const signalFile = path.join(__dirname, 'corrected', `${imageBase}_signal_aligned.nrrd`);
                    const bgFile = path.join(__dirname, 'corrected', `${imageBase}_background_aligned.nrrd`);
                    const stageProgress = getJobStageProgress(imageBase);

                    if (fs.existsSync(signalFile) && fs.existsSync(bgFile)) {
                        console.log(`Existing alignment completed for: ${imageBase}`);
                        alignmentStatus[imageBase] = {
                            ...alignmentStatus[imageBase],
                            status: 'completed',
                            progress: 100,
                            current_stage: 'completed',
                            stages: stageProgress?.stages || alignmentStatus[imageBase].stages,
                            error: '',
                            completed_at: stageProgress?.completed_at || new Date().toISOString()
                        };
                    } else {
                        console.log(`Existing alignment appears to have failed for: ${imageBase}`);
                        alignmentStatus[imageBase] = {
                            ...alignmentStatus[imageBase],
                            status: 'failed',
                            progress: 0,
                            current_stage: stageProgress?.current_stage || 'unknown',
                            stages: stageProgress?.stages || alignmentStatus[imageBase].stages,
                            error: stageProgress?.error || 'Process ended without producing output',
                            completed_at: new Date().toISOString()
                        };
                    }
                    imageSet.delete(imageBase);
                    if (currentAlignment === imageBase) {
                        currentAlignment = null;
                    }
                    writeAlignmentState();
                }
            }

            // If all monitored processes are done, stop polling and process queue
            if (imageSet.size === 0) {
                clearInterval(checkInterval);
                setTimeout(processAlignmentQueue, 1000);
            }
        });
    }, 10000); // Check every 10 seconds
}

// Process alignment queue
function processAlignmentQueue() {
    if (currentAlignment || alignmentQueue.length === 0) {
        return;
    }

    // Check for any running CMTK processes before starting a new one
    exec('ps aux | grep -E "CMTK/bin/(registration|warp|reformatx|make_initial_affine)" | grep -v grep', (error, stdout) => {
        if (!error && stdout.trim()) {
            console.log('CMTK process already running, waiting...');
            setTimeout(processAlignmentQueue, 30000);
            return;
        }

        startNextAlignment();
    });
}

function startNextAlignment() {
    if (currentAlignment || alignmentQueue.length === 0) {
        return;
    }

    currentAlignment = alignmentQueue.shift();
    const imageBase = currentAlignment;
    alignmentStatus[imageBase] = {
        ...alignmentStatus[imageBase],
        status: 'processing',
        progress: 0,
        current_stage: 'initializing',
        stages: {},
        error: '',
        started_at: new Date().toISOString()
    };
    writeAlignmentState();

    console.log(`Starting alignment for: ${imageBase}`);

    // Set OUTPUT_DIR for Docker deployments (or when env is set)
    const procEnv = { ...process.env };
    if (process.env.OUTPUT_DIR) {
        procEnv.OUTPUT_DIR = process.env.OUTPUT_DIR;
    } else if (fs.existsSync('/data/output')) {
        procEnv.OUTPUT_DIR = '/data/output';
    }

    const proc = spawn('bash', ['./align_single_cmtk.sh', imageBase], {
        cwd: __dirname,
        env: procEnv,
        stdio: ['ignore', 'pipe', 'pipe']
    });

    let stderrData = '';

    proc.stdout.on('data', (data) => {
        console.log(`[align ${imageBase}] ${data.toString().trim()}`);
    });

    proc.stderr.on('data', (data) => {
        stderrData += data.toString();
        console.error(`[align ${imageBase} ERR] ${data.toString().trim()}`);
    });

    // Poll per-job progress file every 5 seconds
    const progressInterval = setInterval(() => {
        if (alignmentStatus[imageBase]?.status !== 'processing') {
            clearInterval(progressInterval);
            return;
        }
        const stageProgress = getJobStageProgress(imageBase);
        if (stageProgress && alignmentStatus[imageBase]) {
            const stage = stageProgress.current_stage || 'initializing';
            alignmentStatus[imageBase].progress = STAGE_PROGRESS[stage] || 0;
            alignmentStatus[imageBase].current_stage = stage;
            alignmentStatus[imageBase].stages = stageProgress.stages;
            alignmentStatus[imageBase].started_at = stageProgress.started_at || alignmentStatus[imageBase].started_at;
        }
    }, 5000);

    proc.on('close', (code) => {
        clearInterval(progressInterval);
        const stageProgress = getJobStageProgress(imageBase);

        if (code !== 0) {
            console.error(`Alignment failed for ${imageBase} (exit code ${code})`);
            alignmentStatus[imageBase] = {
                ...alignmentStatus[imageBase],
                status: 'failed',
                current_stage: stageProgress?.current_stage || 'unknown',
                stages: stageProgress?.stages || {},
                error: stageProgress?.error || stderrData.slice(-500) || `Exit code ${code}`,
                completed_at: new Date().toISOString()
            };
        } else {
            console.log(`Alignment completed for: ${imageBase}`);
            alignmentStatus[imageBase] = {
                ...alignmentStatus[imageBase],
                status: 'completed',
                progress: 100,
                current_stage: 'completed',
                stages: stageProgress?.stages || {},
                error: '',
                completed_at: stageProgress?.completed_at || new Date().toISOString()
            };
        }
        currentAlignment = null;
        writeAlignmentState();
        setTimeout(processAlignmentQueue, 1000);
    });

    proc.on('error', (err) => {
        clearInterval(progressInterval);
        console.error(`Failed to start alignment for ${imageBase}:`, err);
        alignmentStatus[imageBase] = {
            ...alignmentStatus[imageBase],
            status: 'failed',
            progress: 0,
            error: err.message,
            completed_at: new Date().toISOString()
        };
        currentAlignment = null;
        writeAlignmentState();
        setTimeout(processAlignmentQueue, 1000);
    });
}

// API endpoints
app.get('/api/images', (req, res) => {
    const imagesDir = path.join(__dirname, 'Images');
    console.log(`[/api/images] Scanning directory: ${imagesDir}`);
    const getTiffs = (dir) => {
        let tiffs = [];
        const items = fs.readdirSync(dir);
        for (const item of items) {
            const fullPath = path.join(dir, item);
            const stat = fs.statSync(fullPath);
            if (stat.isDirectory()) {
                tiffs = tiffs.concat(getTiffs(fullPath));
            } else if ((item.endsWith('.tif') || item.endsWith('.tiff')) && !item.includes('.original')) {
                tiffs.push(path.relative(imagesDir, fullPath).replace(/\.tif$/, '').replace(/\.tiff$/, ''));
            }
        }
        return tiffs;
    };
    try {
        const images = getTiffs(imagesDir);
        console.log(`[/api/images] Found ${images.length} images: ${JSON.stringify(images)}`);
        res.json(images);
    } catch (err) {
        console.error(`[/api/images] Error scanning directory: ${err.message}`);
        console.error(`[/api/images] Stack: ${err.stack}`);
        res.status(500).json({ error: 'Unable to read Images directory' });
    }
});

app.get('/api/saved', (req, res) => {
    res.json(readOrientations());
});

app.get('/api/image', (req, res) => {
    const imageName = req.query.name;
    const bgChannel = parseInt(req.query.bg_channel) || 1;
    if (!imageName) {
        return res.status(400).json({ error: 'Missing image name' });
    }
    const cmd = `source venv/bin/activate && python get_image_data.py ${shellEscape(imageName)} ${bgChannel}`;
    console.log(`[/api/image] Request for: ${imageName} (bg_channel=${bgChannel})`);
    console.log(`[/api/image] Executing: ${cmd}`);
    exec(cmd, { shell: '/bin/bash', maxBuffer: 50 * 1024 * 1024, timeout: 120000 }, (error, stdout, stderr) => {
        if (stderr) {
            console.log(`[/api/image] stderr: ${stderr}`);
        }
        if (error) {
            console.error(`[/api/image] Error: ${error.message}`);
            console.error(`[/api/image] Exit code: ${error.code}`);
            console.error(`[/api/image] stderr: ${stderr}`);
            return res.status(500).json({ error: 'Failed to get image data', detail: stderr || error.message });
        }
        try {
            const data = JSON.parse(stdout);
            console.log(`[/api/image] Success for ${imageName} — shape: ${JSON.stringify(data.image_info?.shape)}, template: ${data.automated_analysis?.detected_template}`);
            res.json(data);
        } catch (e) {
            console.error(`[/api/image] JSON parse error: ${e}`);
            console.error(`[/api/image] stdout (first 500 chars): ${stdout.substring(0, 500)}`);
            res.status(500).json({ error: 'Invalid JSON response' });
        }
    });
});

app.post('/api/rotate', (req, res) => {
    const imageName = req.query.name;
    const { rotations } = req.body;
    if (!imageName || !rotations) {
        return res.status(400).json({ error: 'Missing image name or rotations' });
    }
    const rotStr = JSON.stringify(rotations);
    const cmd = `source venv/bin/activate && python apply_rotation.py ${shellEscape(imageName)} ${shellEscape(rotStr)}`;
    console.log(`[/api/rotate] Request for: ${imageName} rotations=${rotStr}`);
    console.log(`[/api/rotate] Executing: ${cmd}`);
    exec(cmd, { shell: '/bin/bash', timeout: 120000 }, (error, stdout, stderr) => {
        if (stdout) console.log(`[/api/rotate] stdout: ${stdout}`);
        if (stderr) console.log(`[/api/rotate] stderr: ${stderr}`);
        if (error) {
            console.error(`[/api/rotate] Error: ${error.message}`);
            console.error(`[/api/rotate] Exit code: ${error.code}`);
            return res.status(500).json({ error: 'Failed to apply rotation', detail: stderr || error.message });
        }

        // Reset saved rotations to 0 since the image file has been rotated
        const saved = readOrientations();
        if (saved[imageName] && saved[imageName].manual_corrections) {
            saved[imageName].manual_corrections.rotations = { x: 0, y: 0, z: 0 };
            writeOrientations(saved);
        }

        console.log(`[/api/rotate] Success for ${imageName}`);
        res.json({ success: true });
    });
});

app.post('/api/reset', (req, res) => {
    const imageName = req.query.name;
    if (!imageName) {
        return res.status(400).json({ error: 'Missing image name' });
    }
    const cmd = `source venv/bin/activate && python reset_rotation.py ${shellEscape(imageName)}`;
    console.log(`[/api/reset] Request for: ${imageName}`);
    console.log(`[/api/reset] Executing: ${cmd}`);
    exec(cmd, { shell: '/bin/bash', timeout: 60000 }, (error, stdout, stderr) => {
        if (stdout) console.log(`[/api/reset] stdout: ${stdout}`);
        if (stderr) console.log(`[/api/reset] stderr: ${stderr}`);
        if (error) {
            console.error(`[/api/reset] Error: ${error.message}`);
            console.error(`[/api/reset] Exit code: ${error.code}`);
            return res.status(500).json({ error: 'Failed to reset rotation', detail: stderr || error.message });
        }
        console.log(`[/api/reset] Success for ${imageName}`);
        res.json({ success: true });
    });
});

app.post('/api/save', (req, res) => {
    const imageName = req.query.name;
    const { template, template_correct, background_channel, rotations } = req.body;
    if (!imageName) {
        return res.status(400).json({ error: 'Missing image name' });
    }

    console.log(`[/api/save] Saving assessment for: ${imageName} template=${template} bg_channel=${background_channel} rotations=${JSON.stringify(rotations)}`);

    const saved = readOrientations();
    const entry = saved[imageName] || {};

    // Merge manual corrections without overwriting image_info or automated_analysis
    entry.manual_corrections = {
        template: template || '',
        template_correct: !!template_correct,
        background_channel: background_channel !== undefined ? background_channel : 1,
        rotations: rotations || { x: 0, y: 0, z: 0 }
    };
    entry.saved_at = new Date().toISOString();

    saved[imageName] = entry;
    writeOrientations(saved);
    console.log(`[/api/save] Success for ${imageName}`);
    res.json({ success: true });
});

app.post('/api/approve', (req, res) => {
    const imageName = req.query.name;
    if (!imageName) {
        return res.status(400).json({ error: 'Missing image name' });
    }

    console.log(`[/api/approve] Approving: ${imageName}`);
    const saved = readOrientations();
    if (!saved[imageName]) {
        console.error(`[/api/approve] Image not saved yet: ${imageName}`);
        return res.status(400).json({ error: 'Image not saved yet - save changes first' });
    }

    saved[imageName].approved = true;
    saved[imageName].approved_at = new Date().toISOString();

    writeOrientations(saved);

    console.log(`[/api/approve] Success for ${imageName}`);
    res.json({ success: true, message: 'Image approved for review' });
});

app.post('/api/queue-alignment', (req, res) => {
    const imageBase = req.body.image_base;
    console.log(`[/api/queue-alignment] Request for: ${imageBase}`);
    if (!imageBase) {
        return res.status(400).json({ error: 'Missing image_base' });
    }

    // Prevent duplicate preparation
    if (preparingImages.has(imageBase)) {
        console.log(`[/api/queue-alignment] Already preparing: ${imageBase}`);
        return res.json({ success: true, message: 'Image is already being prepared for alignment' });
    }

    // Prevent re-queuing if already queued/processing
    if (alignmentQueue.includes(imageBase) || alignmentStatus[imageBase]?.status === 'processing') {
        console.log(`[/api/queue-alignment] Already queued/processing: ${imageBase}`);
        return res.json({ success: true, message: 'Image is already queued or processing' });
    }

    const saved = readOrientations();
    // Find the image by base name
    const imageKey = Object.keys(saved).find(key => key.split('/').pop() === imageBase);
    console.log(`[/api/queue-alignment] imageKey lookup: ${imageBase} → ${imageKey || 'NOT FOUND'}`);
    if (!imageKey || !saved[imageKey].approved) {
        console.error(`[/api/queue-alignment] Not approved or not found: imageBase=${imageBase} imageKey=${imageKey} approved=${saved[imageKey]?.approved}`);
        return res.status(400).json({ error: 'Image must be approved before queuing for alignment' });
    }

    // Check if NRRD file exists
    const nrrdFile = path.join(__dirname, 'nrrd_output', `${imageBase}.nrrd`);
    const tiffFile = path.join(__dirname, 'Images', imageKey + '.tif');
    const signalFile = path.join(__dirname, 'channels', `${imageBase}_signal.nrrd`);
    const backgroundFile = path.join(__dirname, 'channels', `${imageBase}_background.nrrd`);

    const needsNrrd = !fs.existsSync(nrrdFile);
    const needsChannels = !fs.existsSync(signalFile) || !fs.existsSync(backgroundFile);
    console.log(`[/api/queue-alignment] Prerequisites: nrrd=${nrrdFile} exists=${!needsNrrd}, signal=${signalFile} exists=${fs.existsSync(signalFile)}, bg=${backgroundFile} exists=${fs.existsSync(backgroundFile)}`);

    // If all prerequisites exist, queue immediately
    if (!needsNrrd && !needsChannels) {
        console.log(`[/api/queue-alignment] All prerequisites exist, queuing immediately: ${imageBase}`);
        queueAlignment(imageBase);
        return res.json({ success: true, message: 'Image queued for CMTK alignment' });
    }

    // Prerequisites need to be created - respond immediately and prepare in background
    if (needsNrrd && !fs.existsSync(tiffFile)) {
        console.error(`[/api/queue-alignment] Source TIFF not found: ${tiffFile}`);
        return res.status(400).json({ error: 'Source TIFF file not found' });
    }

    console.log(`[/api/queue-alignment] Starting preparation for ${imageBase} (needsNrrd=${needsNrrd}, needsChannels=${needsChannels})`);
    preparingImages.add(imageBase);
    alignmentStatus[imageBase] = { status: 'preparing', progress: 0, error: '', queued_at: new Date().toISOString() };
    writeAlignmentState();
    res.json({ success: true, message: 'Image preparation started - will be queued automatically when ready' });

    // Run preparation in the background
    prepareAndQueue(imageBase, needsNrrd);
});

function prepareAndQueue(imageBase, needsNrrd) {

    function createChannelsThenQueue() {
        const signalFile = path.join(__dirname, 'channels', `${imageBase}_signal.nrrd`);
        const backgroundFile = path.join(__dirname, 'channels', `${imageBase}_background.nrrd`);

        if (fs.existsSync(signalFile) && fs.existsSync(backgroundFile)) {
            preparingImages.delete(imageBase);
            queueAlignment(imageBase);
            return;
        }

        const splitCmd = 'source venv/bin/activate && python3 split_channels.py ' + shellEscape(imageBase);
        console.log(`[prepareAndQueue] Channel files missing for ${imageBase}, creating them...`);
        console.log(`[prepareAndQueue] Executing: ${splitCmd}`);
        const splitProcess = spawn('bash', ['-c', splitCmd], { cwd: __dirname });

        splitProcess.stdout.on('data', (data) => console.log(`[split_channels ${imageBase}] ${data.toString().trim()}`));
        splitProcess.stderr.on('data', (data) => console.error(`[split_channels ${imageBase} ERR] ${data.toString().trim()}`));

        splitProcess.on('close', (code) => {
            console.log(`[split_channels ${imageBase}] Exited with code ${code}`);
            preparingImages.delete(imageBase);
            if (code !== 0) {
                console.error(`[prepareAndQueue] Failed to create channel files for ${imageBase} (exit code ${code})`);
                alignmentStatus[imageBase] = { status: 'failed', progress: 0, error: 'Failed to create channel files', completed_at: new Date().toISOString() };
                writeAlignmentState();
                return;
            }
            queueAlignment(imageBase);
        });

        splitProcess.on('error', (err) => {
            preparingImages.delete(imageBase);
            console.error(`[prepareAndQueue] Error running split_channels.py for ${imageBase}: ${err}`);
            alignmentStatus[imageBase] = { status: 'failed', progress: 0, error: 'Failed to create channel files', completed_at: new Date().toISOString() };
            writeAlignmentState();
        });
    }

    if (needsNrrd) {
        const convertCmd = 'source venv/bin/activate && python3 convert_tiff_to_nrrd.py ' + shellEscape(imageBase);
        console.log(`[prepareAndQueue] NRRD file missing for ${imageBase}, converting from TIFF...`);
        console.log(`[prepareAndQueue] Executing: ${convertCmd}`);
        const convertProcess = spawn('bash', ['-c', convertCmd], { cwd: __dirname });

        convertProcess.stdout.on('data', (data) => console.log(`[convert_tiff ${imageBase}] ${data.toString().trim()}`));
        convertProcess.stderr.on('data', (data) => console.error(`[convert_tiff ${imageBase} ERR] ${data.toString().trim()}`));

        convertProcess.on('close', (code) => {
            console.log(`[convert_tiff ${imageBase}] Exited with code ${code}`);
            if (code !== 0) {
                preparingImages.delete(imageBase);
                console.error(`[prepareAndQueue] Failed to convert TIFF to NRRD for ${imageBase} (exit code ${code})`);
                alignmentStatus[imageBase] = { status: 'failed', progress: 0, error: 'Failed to convert TIFF to NRRD', completed_at: new Date().toISOString() };
                writeAlignmentState();
                return;
            }
            createChannelsThenQueue();
        });

        convertProcess.on('error', (err) => {
            preparingImages.delete(imageBase);
            console.error(`[prepareAndQueue] Error running convert_tiff_to_nrrd.py for ${imageBase}: ${err}`);
            alignmentStatus[imageBase] = { status: 'failed', progress: 0, error: 'Failed to convert TIFF to NRRD', completed_at: new Date().toISOString() };
            writeAlignmentState();
        });
    } else {
        console.log(`[prepareAndQueue] NRRD exists, proceeding to channel splitting for ${imageBase}`);
        createChannelsThenQueue();
    }
}

function queueAlignment(imageBase) {
    if (!alignmentQueue.includes(imageBase) && alignmentStatus[imageBase]?.status !== 'processing' && alignmentStatus[imageBase]?.status !== 'completed') {
        alignmentQueue.push(imageBase);
        alignmentStatus[imageBase] = { status: 'queued', progress: 0, error: '', queued_at: new Date().toISOString() };
        console.log(`Added ${imageBase} to alignment queue`);
        writeAlignmentState();
        processAlignmentQueue();
    }
}

app.get('/api/alignment-status', (req, res) => {
    const queuePosition = {};
    alignmentQueue.forEach((item, index) => {
        queuePosition[item] = index + 1;
    });

    const jobs = Object.keys(alignmentStatus).map(imageBase => {
        const job = { ...alignmentStatus[imageBase] };
        // Merge per-job progress file for active jobs
        if (job.status === 'processing') {
            const stageProgress = getJobStageProgress(imageBase);
            if (stageProgress) {
                job.stages = stageProgress.stages || job.stages;
                job.current_stage = stageProgress.current_stage || job.current_stage;
                job.started_at = stageProgress.started_at || job.started_at;
                job.progress = STAGE_PROGRESS[job.current_stage] || job.progress;
            }
        }
        return {
            image_base: imageBase,
            ...job,
            stage_labels: STAGE_LABELS,
            queue_position: queuePosition[imageBase] || null,
            is_current: currentAlignment === imageBase
        };
    });

    res.json(jobs);
});

app.get('/api/alignment-thumbnails', (req, res) => {
    const imageBase = req.query.image_base;
    if (!imageBase) {
        return res.status(400).json({ error: 'Missing image_base parameter' });
    }

    const thumbnailFile = path.join(__dirname, 'corrected', `${imageBase}_alignment_thumbnails.json`);
    if (!fs.existsSync(thumbnailFile)) {
        return res.status(404).json({ error: 'Thumbnails not found - alignment may not be complete' });
    }

    try {
        const thumbnails = JSON.parse(fs.readFileSync(thumbnailFile, 'utf8'));
        res.json(thumbnails);
    } catch (err) {
        res.status(500).json({ error: 'Failed to read thumbnails' });
    }
});

app.post('/api/reset-alignment', (req, res) => {
    const imageBase = req.body.image_base;
    if (!imageBase) {
        return res.status(400).json({ error: 'Missing image_base' });
    }

    if (alignmentStatus[imageBase]) {
        delete alignmentStatus[imageBase];
    }

    // Remove from queue if present
    const index = alignmentQueue.indexOf(imageBase);
    if (index > -1) {
        alignmentQueue.splice(index, 1);
    }

    writeAlignmentState();
    res.json({ success: true, message: `Alignment status reset for ${imageBase}` });
});

// Regenerate thumbnails for a completed alignment (adds overlay + signal thumbs)
app.post('/api/regenerate-thumbnails', (req, res) => {
    const imageBase = req.body.image_base;
    if (!imageBase) {
        return res.status(400).json({ error: 'Missing image_base' });
    }

    console.log(`[/api/regenerate-thumbnails] Regenerating for: ${imageBase}`);

    // Determine template and file paths
    const isVNC = imageBase.includes('VNC');
    const template = isVNC ? 'JRCVNC2018U_template_lps.nrrd' : 'JRC2018U_template_lps.nrrd';
    const outputBgFile = path.join(__dirname, 'corrected', `${imageBase}_background_aligned.nrrd`);
    const outputSignalFile = path.join(__dirname, 'corrected', `${imageBase}_signal_aligned.nrrd`);
    const outputJson = path.join(__dirname, 'corrected', `${imageBase}_alignment_thumbnails.json`);

    if (!fs.existsSync(outputBgFile)) {
        return res.status(400).json({ error: 'Aligned background file not found — alignment may not be complete' });
    }

    const timestamp = new Date().toISOString();
    const signalArg = fs.existsSync(outputSignalFile) ? shellEscape(outputSignalFile) : "''";

    const cmd = `source venv/bin/activate && python3 -c "
import sys, json, base64, io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import nrrd
import numpy as np

template_path = sys.argv[1]
output_bg_path = sys.argv[2]
image_base = sys.argv[3]
template_name = sys.argv[4]
ts = sys.argv[5]
output_json = sys.argv[6]
output_signal_path = sys.argv[7] if len(sys.argv) > 7 and sys.argv[7] else None

def to_png_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

def generate_thumbnail(data, title='', figsize=(4,4)):
    fig, ax = plt.subplots(figsize=figsize, dpi=100)
    ax.imshow(data, cmap='gray', aspect='auto')
    ax.set_title(title)
    ax.axis('off')
    return to_png_base64(fig)

def normalise(arr):
    mn, mx = arr.min(), arr.max()
    if mx == mn:
        return np.zeros_like(arr, dtype=np.float32)
    return (arr - mn).astype(np.float32) / (mx - mn)

def generate_overlay(template_proj, aligned_proj, title='', figsize=(4,4)):
    t = normalise(template_proj)
    a = normalise(aligned_proj)
    h, w = t.shape[:2]
    if a.shape != t.shape:
        from scipy.ndimage import zoom
        zoom_factors = (h / a.shape[0], w / a.shape[1])
        a = zoom(a, zoom_factors, order=1)
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    rgb[..., 0] = t
    rgb[..., 1] = a
    rgb[..., 2] = t
    fig, ax = plt.subplots(figsize=figsize, dpi=100)
    ax.imshow(np.clip(rgb, 0, 1), aspect='auto')
    ax.set_title(title)
    ax.axis('off')
    return to_png_base64(fig)

template_data, _ = nrrd.read(template_path)
aligned_bg_data, _ = nrrd.read(output_bg_path)

axes = [0, 1, 2]
template_projs = [np.max(template_data, axis=ax) for ax in axes]
aligned_projs  = [np.max(aligned_bg_data, axis=ax) for ax in axes]

thumbnails = {}
for i, axis in enumerate(['x', 'y', 'z']):
    thumbnails[f'{axis}_template'] = generate_thumbnail(template_projs[i], f'Template {axis.upper()}-axis')
    thumbnails[f'{axis}_aligned']  = generate_thumbnail(aligned_projs[i],  f'Aligned {axis.upper()}-axis')
    thumbnails[f'{axis}_overlay']  = generate_overlay(template_projs[i], aligned_projs[i], f'Overlay {axis.upper()}-axis')

if output_signal_path:
    try:
        signal_data, _ = nrrd.read(output_signal_path)
        signal_projs = [np.max(signal_data, axis=ax) for ax in axes]
        for i, axis in enumerate(['x', 'y', 'z']):
            thumbnails[f'{axis}_signal'] = generate_thumbnail(signal_projs[i], f'Signal {axis.upper()}-axis')
        print('Signal thumbnails included')
    except Exception as e:
        print(f'Warning: could not load signal file: {e}')

result = {
    'image_base': image_base,
    'template': template_name,
    'thumbnails': thumbnails,
    'aligned_at': ts
}

with open(output_json, 'w') as f:
    json.dump(result, f, indent=2)

print('Thumbnails regenerated successfully')
" ${shellEscape(template)} ${shellEscape(outputBgFile)} ${shellEscape(imageBase)} ${shellEscape(template)} ${shellEscape(timestamp)} ${shellEscape(outputJson)} ${signalArg}`;

    exec(cmd, { shell: '/bin/bash', timeout: 300000, maxBuffer: 50 * 1024 * 1024 }, (error, stdout, stderr) => {
        if (stdout) console.log(`[regenerate-thumbnails] ${stdout.trim()}`);
        if (stderr) console.log(`[regenerate-thumbnails stderr] ${stderr.trim()}`);
        if (error) {
            console.error(`[regenerate-thumbnails] Error: ${error.message}`);
            return res.status(500).json({ error: 'Failed to regenerate thumbnails', detail: stderr || error.message });
        }
        console.log(`[regenerate-thumbnails] Success for ${imageBase}`);
        res.json({ success: true, message: 'Thumbnails regenerated with overlay and signal views' });
    });
});

app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
    // Load persisted state, then detect any running alignment processes
    loadPersistedState();
    detectRunningAlignments();
});
