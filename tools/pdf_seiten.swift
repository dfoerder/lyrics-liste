// Rendert jede Seite eines PDFs als PNG. Der Inhalt bleibt unverändert; nur leerer
// weißer Rand rundherum wird abgeschnitten (bis auf einen schmalen Rest), damit die
// Noten auf dem iPhone nicht winzig in einer großen weißen Seite stehen.
// Aufruf: swift pdf_seiten.swift <pdf> <zielordner> <faktor>
// Faktor 2 = 144 dpi – genug für den 3-fach-Zoom der App auf dem iPhone.
import AppKit
import Foundation
import PDFKit

let args = CommandLine.arguments
guard args.count == 4,
      let doc = PDFDocument(url: URL(fileURLWithPath: args[1])),
      let scale = Double(args[3]) else {
    FileHandle.standardError.write("Aufruf: pdf_seiten.swift <pdf> <zielordner> <faktor>\n".data(using: .utf8)!)
    exit(1)
}
let outDir = URL(fileURLWithPath: args[2])
let inkThreshold: UInt8 = 200   // dunkler als das zählt als Inhalt
let padding = 24                // verbleibender Rand in Pixeln (~4 mm bei 144 dpi)

// Kleinstes Rechteck um alle nicht-weißen Pixel (Zeile 0 = oberer Bildrand), nil bei leerer Seite
func contentBox(_ ctx: CGContext, width w: Int, height h: Int) -> CGRect? {
    guard let raw = ctx.data else { return nil }
    let px = raw.bindMemory(to: UInt8.self, capacity: ctx.bytesPerRow * h)
    var minX = w, minY = h, maxX = -1, maxY = -1
    for y in 0..<h {
        let row = y * ctx.bytesPerRow
        for x in 0..<w where px[row + x] < inkThreshold {
            if x < minX { minX = x }
            if x > maxX { maxX = x }
            if y < minY { minY = y }
            maxY = y
        }
    }
    guard maxX >= 0 else { return nil }
    let x0 = max(0, minX - padding), y0 = max(0, minY - padding)
    let x1 = min(w, maxX + 1 + padding), y1 = min(h, maxY + 1 + padding)
    return CGRect(x: x0, y: y0, width: x1 - x0, height: y1 - y0)
}

for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let box = page.bounds(for: .mediaBox)
    let w = Int(box.width * scale), h = Int(box.height * scale)
    // Graustufen: Noten sind schwarz-weiß, das hält die Bilder klein
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceGray(),
                              bitmapInfo: CGImageAlphaInfo.none.rawValue) else { exit(2) }
    ctx.setFillColor(gray: 1, alpha: 1)
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    guard let full = ctx.makeImage() else { exit(3) }
    let image = contentBox(ctx, width: w, height: h).flatMap { full.cropping(to: $0) } ?? full
    guard let png = NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:]) else { exit(3) }
    let url = outDir.appendingPathComponent(String(format: "seite-%02d.png", i + 1))
    do { try png.write(to: url) } catch { exit(4) }
    print(url.path)
}
