const fs = require('fs');
const PptxGenJS = require('pptxgenjs');

// Parse from stdin
const inputData = fs.readFileSync(0, 'utf8');
const { content, outputPath, title, theme } = JSON.parse(inputData);

const pptx = new PptxGenJS();
pptx.layout = 'LAYOUT_16x9';

// Define theme colors based on Skill documentation
const palettes = {
    "midnight": { bg: "1E2761", accent: "CADCFC", text: "FFFFFF" },
    "forest": { bg: "2C5F2D", accent: "97BC62", text: "F5F5F5" },
    "default": { bg: "F2F2F2", accent: "36454F", text: "212121" }
};

const selectedPalette = palettes[theme] || palettes["default"];

// Add Title Slide
let slide = pptx.addSlide();
slide.background = { fill: selectedPalette.bg };
slide.addText(title || "AI Generated Presentation", { 
    x: 1, y: 3, w: "80%", fontSize: 44, color: selectedPalette.text, align: "center", bold: true 
});

// Simple Markdown to Slides parser
// Each ## is a new slide
const lines = content.split('\n');
let currentSlide = null;
let currentBullets = [];

lines.forEach(line => {
    line = line.trim();
    if (line.startsWith('## ')) {
        // If we were collecting bullets for previous slide, add them now
        if (currentSlide && currentBullets.length > 0) {
            currentSlide.addText(currentBullets.join('\n'), { 
                x: 0.5, y: 1.5, w: "90%", fontSize: 18, color: "333333", bullet: true 
            });
            currentBullets = [];
        }
        
        // Create new slide
        currentSlide = pptx.addSlide();
        currentSlide.addText(line.replace('## ', ''), { 
            x: 0.5, y: 0.5, w: "90%", fontSize: 32, bold: true, color: selectedPalette.bg 
        });
        // Decorative line
        currentSlide.addShape(pptx.ShapeType.rect, { 
            x: 0.5, y: 1.1, w: 9, h: 0.05, fill: { color: selectedPalette.accent } 
        });
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
        if (currentSlide) {
            currentBullets.push(line.substring(2));
        }
    } else if (line.length > 0) {
        if (currentSlide) {
            currentSlide.addText(line, { x: 0.5, y: 1.5 + (currentBullets.length * 0.4), w: "90%", fontSize: 14 });
        }
    }
});

// Add last slide's bullets
if (currentSlide && currentBullets.length > 0) {
    currentSlide.addText(currentBullets.join('\n'), { 
        x: 0.5, y: 1.5, w: "90%", fontSize: 18, color: "333333", bullet: true 
    });
}

pptx.writeFile({ fileName: outputPath }).then(fileName => {
    console.log(JSON.stringify({ success: true, path: fileName }));
}).catch(err => {
    console.error(JSON.stringify({ success: false, error: err.message }));
    process.exit(1);
});
