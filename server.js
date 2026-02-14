const express = require('express');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;
const ORIENTATIONS_FILE = path.join(__dirname, 'orientations.json');

// Middleware
app.use(express.json());
app.use(express.static('public'));

// Alignment queue
let alignmentQueue = [];
let currentAlignment = null;
let alignmentStatus = {}; // image_base -> { status: 'queued|processing|completed|failed', progress: 0-100, error: '' }

function readOrientations() {
    if (fs.existsSync(ORIENTATIONS_FILE)) {
        return JSON.parse(fs.readFileSync(ORIENTATIONS_FILE, 'utf8'));
    }
    return {};
}

function writeOrientations(data) {
    fs.writeFileSync(ORIENTATIONS_FILE, JSON.stringify(data, null, 2));
}

// Process alignment queue
function processAlignmentQueue() {
    if (currentAlignment || alignmentQueue.length === 0) {
        return;
    }

    currentAlignment = alignmentQueue.shift();
    const imageBase = currentAlignment;
    alignmentStatus[imageBase] = { status: 'processing', progress: 0, error: '' };

    console.log(`Starting alignment for: ${imageBase}`);

    const timestamp = new Date().toISOString();
    exec(`./align_single_cmtk.sh "${imageBase}"`, { timeout: 600000 }, (error, stdout, stderr) => {
        if (error) {
            console.error(`Alignment failed for ${imageBase}:`, error);
            alignmentStatus[imageBase] = { 
                status: 'failed', 
                progress: 0, 
                error: error.message || 'Unknown error',
                completed_at: new Date().toISOString()
            };
        } else {
            console.log(`Alignment completed for: ${imageBase}`);
            alignmentStatus[imageBase] = { 
                status: 'completed', 
                progress: 100, 
                error: '',
                completed_at: new Date().toISOString()
            };
        }
        currentAlignment = null;
        // Process next in queue
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
    exec(`source venv/bin/activate && python get_image_data.py "${imageName}" ${bgChannel}`, { maxBuffer: 50 * 1024 * 1024, timeout: 120000 }, (error, stdout, stderr) => {
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
    exec(`source venv/bin/activate && python apply_rotation.py "${imageName}" '${rotStr}'`, { timeout: 120000 }, (error, stdout, stderr) => {
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
    exec(`source venv/bin/activate && python reset_rotation.py "${imageName}"`, { timeout: 60000 }, (error, stdout, stderr) => {
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

    const saved = readOrientations();
    // Find the image by base name
    const imageKey = Object.keys(saved).find(key => key.split('/').pop() === imageBase);
    if (!imageKey || !saved[imageKey].approved) {
        return res.status(400).json({ error: 'Image must be approved before queuing for alignment' });
    }

    // Check if NRRD file exists, create it if not
    const nrrdFile = path.join(__dirname, 'nrrd_output', `${imageBase}.nrrd`);
    const tiffFile = path.join(__dirname, 'Images', imageKey + '.tif');

    if (!fs.existsSync(nrrdFile)) {
        if (!fs.existsSync(tiffFile)) {
            return res.status(400).json({ error: 'Source TIFF file not found' });
        }

        console.log(`NRRD file missing for ${imageBase}, converting from TIFF...`);

        // Run convert_tiff_to_nrrd.py to create the NRRD file
        const { spawn } = require('child_process');
        const convertProcess = spawn('bash', ['-c', 'source venv/bin/activate && python3 convert_tiff_to_nrrd.py ' + imageBase], { cwd: __dirname });

        convertProcess.on('close', (code) => {
            if (code !== 0) {
                console.error(`Failed to convert TIFF to NRRD for ${imageBase}`);
                return res.status(500).json({ error: 'Failed to convert TIFF to NRRD' });
            }

            // Now check/create channel files
            checkAndCreateChannels(imageBase, res);
        });

        convertProcess.on('error', (err) => {
            console.error(`Error running convert_tiff_to_nrrd.py: ${err}`);
            res.status(500).json({ error: 'Failed to convert TIFF to NRRD' });
        });

        return; // Don't queue yet, wait for conversion
    }

    // NRRD exists, check/create channel files
    checkAndCreateChannels(imageBase, res);
});

function checkAndCreateChannels(imageBase, res) {
    const signalFile = path.join(__dirname, 'channels', `${imageBase}_signal.nrrd`);
    const backgroundFile = path.join(__dirname, 'channels', `${imageBase}_background.nrrd`);

    if (!fs.existsSync(signalFile) || !fs.existsSync(backgroundFile)) {
        console.log(`Channel files missing for ${imageBase}, creating them...`);

        // Run split_channels.py to create the channel files
        const { spawn } = require('child_process');
        const splitProcess = spawn('bash', ['-c', 'source venv/bin/activate && python3 split_channels.py ' + imageBase], { cwd: __dirname });

        splitProcess.on('close', (code) => {
            if (code !== 0) {
                console.error(`Failed to create channel files for ${imageBase}`);
                return res.status(500).json({ error: 'Failed to create channel files' });
            }

            // Now queue the alignment
            queueAlignment(imageBase);
            res.json({ success: true, message: 'Channel files created and image queued for CMTK alignment' });
        });

        splitProcess.on('error', (err) => {
            console.error(`Error running split_channels.py: ${err}`);
            res.status(500).json({ error: 'Failed to create channel files' });
        });

        return; // Don't queue yet, wait for channel creation
    }

    // Channel files exist, queue immediately
    queueAlignment(imageBase);
    res.json({ success: true, message: 'Image queued for CMTK alignment' });
}

function queueAlignment(imageBase) {
    if (!alignmentQueue.includes(imageBase) && alignmentStatus[imageBase]?.status !== 'processing' && alignmentStatus[imageBase]?.status !== 'completed') {
        alignmentQueue.push(imageBase);
        alignmentStatus[imageBase] = { status: 'queued', progress: 0, error: '', queued_at: new Date().toISOString() };
        console.log(`Added ${imageBase} to alignment queue`);
        // Start processing if not already running
        processAlignmentQueue();
    }
}

app.get('/api/alignment-status', (req, res) => {
    const queuePosition = {};
    alignmentQueue.forEach((item, index) => {
        queuePosition[item] = index + 1;
    });

    const jobs = Object.keys(alignmentStatus).map(imageBase => ({
        image_base: imageBase,
        ...alignmentStatus[imageBase],
        queue_position: queuePosition[imageBase] || null,
        is_current: currentAlignment === imageBase
    }));

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

app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
});
