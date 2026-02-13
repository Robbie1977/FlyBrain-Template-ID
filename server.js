const express = require('express');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;

// Middleware
app.use(express.json());
app.use(express.static('public'));

// API endpoints
app.get('/api/images', (req, res) => {
    // Get list of images from Images folder
    const imagesDir = path.join(__dirname, 'Images');
    const getTiffs = (dir) => {
        let tiffs = [];
        const items = fs.readdirSync(dir);
        for (const item of items) {
            const fullPath = path.join(dir, item);
            const stat = fs.statSync(fullPath);
            if (stat.isDirectory()) {
                tiffs = tiffs.concat(getTiffs(fullPath));
            } else if (item.endsWith('.tif') || item.endsWith('.tiff')) {
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
    const jsonPath = path.join(__dirname, 'orientations.json');
    if (fs.existsSync(jsonPath)) {
        const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
        res.json(data);
    } else {
        res.json({});
    }
});

app.get('/api/image', (req, res) => {
    const imageName = req.query.name;
    // Call Python script to get image data
    exec(`source venv/bin/activate && python get_image_data.py ${imageName}`, (error, stdout, stderr) => {
        if (error) {
            console.error(`Error: ${error}`);
            return res.status(500).json({ error: 'Failed to get image data' });
        }
        try {
            const data = JSON.parse(stdout);
            res.json(data);
        } catch (e) {
            res.status(500).json({ error: 'Invalid JSON response' });
        }
    });
});

app.post('/api/rotate', (req, res) => {
    const imageName = req.query.name;
    const { rotations } = req.body; // e.g., { x: 90, y: 0, z: 180 }
    // Call Python script to apply rotations
    const rotStr = JSON.stringify(rotations);
    exec(`source venv/bin/activate && python apply_rotation.py "${imageName}" '${rotStr}'`, (error, stdout, stderr) => {
        if (error) {
            console.error(`Error: ${error}`);
            return res.status(500).json({ error: 'Failed to apply rotation' });
        }
        res.json({ success: true });
    });
});

app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
});