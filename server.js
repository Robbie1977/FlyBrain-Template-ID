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
        res.json(images);
    } catch (err) {
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
    exec(`source venv/bin/activate && python get_image_data.py ${shellEscape(imageName)} ${bgChannel}`, { maxBuffer: 50 * 1024 * 1024, timeout: 120000 }, (error, stdout, stderr) => {
        if (error) {
            console.error(`Error: ${error}`);
            console.error(`stderr: ${stderr}`);
            return res.status(500).json({ error: 'Failed to get image data' });
        }
        try {
            const data = JSON.parse(stdout);
            res.json(data);
        } catch (e) {
            console.error(`JSON parse error: ${e}`);
            console.error(`stdout length: ${stdout.length}`);
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
    exec(`source venv/bin/activate && python apply_rotation.py ${shellEscape(imageName)} ${shellEscape(rotStr)}`, { timeout: 120000 }, (error, stdout, stderr) => {
        if (error) {
            console.error(`Error: ${error}`);
            return res.status(500).json({ error: 'Failed to apply rotation' });
        }
        
        // Reset saved rotations to 0 since the image file has been rotated
        const saved = readOrientations();
        if (saved[imageName] && saved[imageName].manual_corrections) {
            saved[imageName].manual_corrections.rotations = { x: 0, y: 0, z: 0 };
            writeOrientations(saved);
        }
        
        res.json({ success: true });
    });
});

app.post('/api/reset', (req, res) => {
    const imageName = req.query.name;
    if (!imageName) {
        return res.status(400).json({ error: 'Missing image name' });
    }
    exec(`source venv/bin/activate && python reset_rotation.py ${shellEscape(imageName)}`, { timeout: 60000 }, (error, stdout, stderr) => {
        if (error) {
            console.error(`Error: ${error}`);
            return res.status(500).json({ error: 'Failed to reset rotation' });
        }
        res.json({ success: true });
    });
});

app.post('/api/save', (req, res) => {
    const imageName = req.query.name;
    const { template, template_correct, background_channel, rotations } = req.body;
    if (!imageName) {
        return res.status(400).json({ error: 'Missing image name' });
    }

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
    res.json({ success: true });
});

app.post('/api/approve', (req, res) => {
    const imageName = req.query.name;
    if (!imageName) {
        return res.status(400).json({ error: 'Missing image name' });
    }

    const saved = readOrientations();
    if (!saved[imageName]) {
        return res.status(400).json({ error: 'Image not saved yet - save changes first' });
    }

    saved[imageName].approved = true;
    saved[imageName].approved_at = new Date().toISOString();

    writeOrientations(saved);

    res.json({ success: true, message: 'Image approved for review' });
});

app.post('/api/queue-alignment', (req, res) => {
    const imageBase = req.body.image_base;
    if (!imageBase) {
        return res.status(400).json({ error: 'Missing image_base' });
    }

    // Prevent duplicate preparation
    if (preparingImages.has(imageBase)) {
        return res.json({ success: true, message: 'Image is already being prepared for alignment' });
    }

    // Prevent re-queuing if already queued/processing
    if (alignmentQueue.includes(imageBase) || alignmentStatus[imageBase]?.status === 'processing') {
        return res.json({ success: true, message: 'Image is already queued or processing' });
    }

    const saved = readOrientations();
    // Find the image by base name
    const imageKey = Object.keys(saved).find(key => key.split('/').pop() === imageBase);
    if (!imageKey || !saved[imageKey].approved) {
        return res.status(400).json({ error: 'Image must be approved before queuing for alignment' });
    }

    // Check if NRRD file exists
    const nrrdFile = path.join(__dirname, 'nrrd_output', `${imageBase}.nrrd`);
    const tiffFile = path.join(__dirname, 'Images', imageKey + '.tif');
    const signalFile = path.join(__dirname, 'channels', `${imageBase}_signal.nrrd`);
    const backgroundFile = path.join(__dirname, 'channels', `${imageBase}_background.nrrd`);

    const needsNrrd = !fs.existsSync(nrrdFile);
    const needsChannels = !fs.existsSync(signalFile) || !fs.existsSync(backgroundFile);

    // If all prerequisites exist, queue immediately
    if (!needsNrrd && !needsChannels) {
        queueAlignment(imageBase);
        return res.json({ success: true, message: 'Image queued for CMTK alignment' });
    }

    // Prerequisites need to be created - respond immediately and prepare in background
    if (needsNrrd && !fs.existsSync(tiffFile)) {
        return res.status(400).json({ error: 'Source TIFF file not found' });
    }

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

        console.log(`Channel files missing for ${imageBase}, creating them...`);
        const splitProcess = spawn('bash', ['-c', 'source venv/bin/activate && python3 split_channels.py ' + shellEscape(imageBase)], { cwd: __dirname });

        splitProcess.on('close', (code) => {
            preparingImages.delete(imageBase);
            if (code !== 0) {
                console.error(`Failed to create channel files for ${imageBase}`);
                alignmentStatus[imageBase] = { status: 'failed', progress: 0, error: 'Failed to create channel files', completed_at: new Date().toISOString() };
                writeAlignmentState();
                return;
            }
            queueAlignment(imageBase);
        });

        splitProcess.on('error', (err) => {
            preparingImages.delete(imageBase);
            console.error(`Error running split_channels.py: ${err}`);
            alignmentStatus[imageBase] = { status: 'failed', progress: 0, error: 'Failed to create channel files', completed_at: new Date().toISOString() };
            writeAlignmentState();
        });
    }

    if (needsNrrd) {
        console.log(`NRRD file missing for ${imageBase}, converting from TIFF...`);
        const convertProcess = spawn('bash', ['-c', 'source venv/bin/activate && python3 convert_tiff_to_nrrd.py ' + shellEscape(imageBase)], { cwd: __dirname });

        convertProcess.on('close', (code) => {
            if (code !== 0) {
                preparingImages.delete(imageBase);
                console.error(`Failed to convert TIFF to NRRD for ${imageBase}`);
                alignmentStatus[imageBase] = { status: 'failed', progress: 0, error: 'Failed to convert TIFF to NRRD', completed_at: new Date().toISOString() };
                writeAlignmentState();
                return;
            }
            createChannelsThenQueue();
        });

        convertProcess.on('error', (err) => {
            preparingImages.delete(imageBase);
            console.error(`Error running convert_tiff_to_nrrd.py: ${err}`);
            alignmentStatus[imageBase] = { status: 'failed', progress: 0, error: 'Failed to convert TIFF to NRRD', completed_at: new Date().toISOString() };
            writeAlignmentState();
        });
    } else {
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

app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
    // Load persisted state, then detect any running alignment processes
    loadPersistedState();
    detectRunningAlignments();
});
