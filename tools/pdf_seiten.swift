// Rendert jede Seite eines PDFs unverändert (ganze Seite, kein Zuschnitt) als PNG.
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
    guard let image = ctx.makeImage(),
          let png = NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:]) else { exit(3) }
    let url = outDir.appendingPathComponent(String(format: "seite-%02d.png", i + 1))
    do { try png.write(to: url) } catch { exit(4) }
    print(url.path)
}
