import Foundation
import PDFKit
import AppKit

// Local, offline PDF QA. No model or document service is contacted.
guard CommandLine.arguments.count == 3 else {
    fputs("usage: swift render_pdf.swift input.pdf output_directory\n", stderr)
    exit(2)
}
let input = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
guard let document = PDFDocument(url: input) else { fatalError("Cannot open PDF") }
var pages: [[String: Any]] = []
var extracted = ""
for index in 0..<document.pageCount {
    guard let page = document.page(at: index) else { fatalError("Missing page") }
    let bounds = page.bounds(for: .mediaBox)
    let scale: CGFloat = 1.65
    let width = Int(ceil(bounds.width * scale))
    let height = Int(ceil(bounds.height * scale))
    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil,
        pixelsWide: width, pixelsHigh: height, bitsPerSample: 8,
        samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
        let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        fatalError("Cannot create bitmap")
    }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    let cg = context.cgContext
    cg.setFillColor(NSColor.white.cgColor)
    cg.fill(CGRect(x: 0, y: 0, width: width, height: height))
    cg.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: cg)
    NSGraphicsContext.restoreGraphicsState()
    guard let data = bitmap.representation(using: .png, properties: [:]) else {
        fatalError("Cannot encode PNG")
    }
    try data.write(to: output.appendingPathComponent(String(format: "page-%02d.png", index + 1)))
    let text = page.string ?? ""
    extracted += "\n\n--- PAGE \(index + 1) ---\n" + text
    let links = page.annotations.compactMap { $0.url?.absoluteString }
    pages.append(["page": index + 1, "width_pt": bounds.width,
        "height_pt": bounds.height, "text_characters": text.count,
        "replacement_characters": text.filter { $0 == "\u{FFFD}" }.count,
        "links": links])
}
try extracted.write(to: output.appendingPathComponent("extracted_text.txt"), atomically: true, encoding: .utf8)
let result: [String: Any] = ["page_count": document.pageCount, "pages": pages]
let json = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
try json.write(to: output.appendingPathComponent("pdf_qa.json"))
print(String(data: json, encoding: .utf8)!)
