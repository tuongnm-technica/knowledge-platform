const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType } = require('docx');

/**
 * Very simple parser to convert "Doc Writer" markdown output to DOCX components.
 * This handles headings (#, ##), bullet points (-), and plain text.
 */
function parseContentToDocx(markdown) {
    const lines = markdown.split('\n');
    const children = [];

    for (let line of lines) {
        line = line.trim();
        if (!line) continue;

        if (line.startsWith('# ')) {
            children.push(new Paragraph({
                text: line.replace('# ', ''),
                heading: HeadingLevel.HEADING_1,
                spacing: { before: 240, after: 240 }
            }));
        } else if (line.startsWith('## ')) {
            children.push(new Paragraph({
                text: line.replace('## ', ''),
                heading: HeadingLevel.HEADING_2,
                spacing: { before: 180, after: 180 }
            }));
        } else if (line.startsWith('### ')) {
            children.push(new Paragraph({
                text: line.replace('### ', ''),
                heading: HeadingLevel.HEADING_3,
                spacing: { before: 120, after: 120 }
            }));
        } else if (line.startsWith('- ') || line.startsWith('* ')) {
            children.push(new Paragraph({
                text: line.substring(2),
                bullet: { level: 0 },
                spacing: { after: 120 }
            }));
        } else {
            children.push(new Paragraph({
                children: [new TextRun(line)],
                spacing: { after: 120 }
            }));
        }
    }
    return children;
}

// Read from stdin or from a temp file argument
const inputData = fs.readFileSync(0, 'utf8');
const { content, outputPath, title } = JSON.parse(inputData);

const doc = new Document({
    sections: [{
        properties: {
            page: {
                size: { width: 11906, height: 16838 } // A4
            }
        },
        children: [
            new Paragraph({
                text: title || "AI Generated Document",
                heading: HeadingLevel.TITLE,
                alignment: "center",
                spacing: { after: 440 }
            }),
            ...parseContentToDocx(content)
        ]
    }]
});

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputPath, buffer);
    console.log(JSON.stringify({ success: true, path: outputPath }));
}).catch(err => {
    console.error(JSON.stringify({ success: false, error: err.message }));
    process.exit(1);
});
