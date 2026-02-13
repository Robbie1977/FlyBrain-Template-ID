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

    // Add to alignment queue
    const imageBase = imageName.split('/').pop(); // Get the base name after the submitter
    if (!alignmentQueue.includes(imageBase) && alignmentStatus[imageBase]?.status !== 'processing' && alignmentStatus[imageBase]?.status !== 'completed') {
        alignmentQueue.push(imageBase);
        alignmentStatus[imageBase] = { status: 'queued', progress: 0, error: '', queued_at: new Date().toISOString() };
        console.log(`Added ${imageBase} to alignment queue`);
        // Start processing if not already running
        processAlignmentQueue();
    }

    res.json({ success: true, message: 'Image approved for CMTK alignment' });
});

app.get('/api/alignment-status', (req, res) => {
    const queuePosition = {};
    alignmentQueue.forEach((item, index) => {
        queuePosition[item] = index + 1;
    });

    const status = Object.keys(alignmentStatus).map(imageBase => ({
        image_base: imageBase,
        ...alignmentStatus[imageBase],
        queue_position: queuePosition[imageBase] || null
    }));

    res.json({
        current: currentAlignment,
        queue: alignmentQueue,
        status: status
    });
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
