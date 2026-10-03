// Lesehilfe zum Abschreiben von Noten: richtet einen Notenscan gerade aus, erkennt die
// Notenlinien und zeichnet ein beschriftetes Tonhöhen-Raster ein (rot = Linie, blau =
// Zwischenraum; B steht für das Vorzeichen der Tonart, nicht für H).
// Ausgabe: je Akkolade (Violin- + Bassschlüssel) drei vergrößerte Ausschnitte
// <ziel>/zeile<N>_<teil>.png zum Ablesen.
//
// Aufruf: swift tools/noten_raster.swift <scan.png|jpg> <zielordner>
// Ein PDF vorher als Bild exportieren, z.B. mit tools/pdf_seiten.swift.
import AppKit
import Foundation

let args = CommandLine.arguments
guard args.count == 3, let src = NSImage(contentsOfFile: args[1]),
      let cg0 = src.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("Aufruf: swift noten_raster.swift <bild> <zielordner>"); exit(1)
}
let outDir = args[2]

func grayPixels(_ img: CGImage) -> (px: [UInt8], w: Int, h: Int) {
    let w = img.width, h = img.height
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w,
                        space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue)!
    ctx.setFillColor(gray: 1, alpha: 1)
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))
    let p = ctx.data!.bindMemory(to: UInt8.self, capacity: w * h)
    return (Array(UnsafeBufferPointer(start: p, count: w * h)), w, h)   // Zeile 0 = oben
}

// 1. Schräglage bestimmen: Winkel, bei dem die Zeilenprojektion am schärfsten ist
let (px0, w0, h0) = grayPixels(cg0)
var dark: [(Double, Double)] = []
for y in stride(from: 0, to: h0, by: 1) {
    for x in stride(from: w0 / 6, to: w0 - 30, by: 3) where px0[y * w0 + x] < 140 { dark.append((Double(x), Double(y))) }
}
var best = (score: -1.0, angle: 0.0)
for k in -40...40 {
    let a = Double(k) * 0.05, t = tan(a * .pi / 180)
    var hist = [Int: Int]()
    for (x, y) in dark { hist[Int((y - x * t).rounded()), default: 0] += 1 }
    let score = hist.values.reduce(0.0) { $0 + Double($1 * $1) }
    if score > best.score { best = (score, a) }
}
print(String(format: "Schräglage: %.2f°", best.angle))

// 2. Gerade ausrichten (Drehung um die Bildmitte, weißer Hintergrund)
let rot = best.angle * .pi / 180          // CoreGraphics: y nach oben, daher gleiches Vorzeichen
let ctxR = CGContext(data: nil, width: w0, height: h0, bitsPerComponent: 8, bytesPerRow: 0,
                     space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
ctxR.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
ctxR.fill(CGRect(x: 0, y: 0, width: w0, height: h0))
ctxR.translateBy(x: Double(w0) / 2, y: Double(h0) / 2)
ctxR.rotate(by: rot)
ctxR.translateBy(x: -Double(w0) / 2, y: -Double(h0) / 2)
ctxR.draw(cg0, in: CGRect(x: 0, y: 0, width: w0, height: h0))
let cg = ctxR.makeImage()!
let (px, w, h) = grayPixels(cg)

// 3. Notenlinien finden und in Fünfergruppen ordnen
var rows: [Int] = []
for y in 0..<h {
    var n = 0
    for x in 0..<w where px[y * w + x] < 140 { n += 1 }
    if Double(n) > Double(w) * 0.45 { rows.append(y) }
}
var lines: [Double] = [], group: [Int] = []
for r in rows {
    if let last = group.last, r - last > 2 { lines.append(Double(group.reduce(0, +)) / Double(group.count)); group = [] }
    group.append(r)
}
if !group.isEmpty { lines.append(Double(group.reduce(0, +)) / Double(group.count)) }
var staves: [[Double]] = []
var i = 0
while i + 4 < lines.count {
    let s = Array(lines[i..<i + 5]), gaps = zip(s.dropFirst(), s).map { $0 - $1 }
    if gaps.max()! - gaps.min()! < 6 { staves.append(s); i += 5 } else { i += 1 }
}
print("Notensysteme: \(staves.count) (abwechselnd Violin-/Bassschlüssel angenommen)")
guard staves.count >= 2 else { print("Zu wenige Notenlinien erkannt."); exit(2) }

// 4. Raster zeichnen (doppelte Größe)
let scale = 2.0, W = Int(Double(w) * scale), H = Int(Double(h) * scale)
let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0,
                    space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
ctx.interpolationQuality = .high
ctx.draw(cg, in: CGRect(x: 0, y: 0, width: W, height: H))
NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
let names = ["C", "D", "E", "F", "G", "A", "B"]
func label(_ step: Int, treble: Bool) -> String {
    let idx = (treble ? 30 : 18) + step          // E4 bzw. G2 = unterste Linie
    return names[((idx % 7) + 7) % 7] + String(idx / 7)
}
for (n, s) in staves.enumerated() {
    let treble = n % 2 == 0, gap = (s[4] - s[0]) / 4
    for step in -6...14 {
        let y = Double(H) - (s[4] - Double(step) * gap / 2) * scale
        let isLine = step % 2 == 0
        let color = isLine ? NSColor(red: 1, green: 0, blue: 0, alpha: 0.35) : NSColor(red: 0, green: 0.4, blue: 1, alpha: 0.35)
        ctx.setStrokeColor(color.cgColor); ctx.setLineWidth(1)
        ctx.move(to: CGPoint(x: 0, y: y)); ctx.addLine(to: CGPoint(x: Double(W), y: y)); ctx.strokePath()
        let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.boldSystemFont(ofSize: 15),
                                                    .foregroundColor: isLine ? NSColor.red : NSColor.blue]
        var x = 4.0
        while x < Double(W) { (label(step, treble: treble) as NSString).draw(at: CGPoint(x: x, y: y - 8), withAttributes: attrs); x += 170 }
    }
}
let full = ctx.makeImage()!

// 5. Je Akkolade drei überlappende Ausschnitte speichern
func save(_ img: CGImage, _ name: String) {
    try! NSBitmapImageRep(cgImage: img).representation(using: .png, properties: [:])!
        .write(to: URL(fileURLWithPath: outDir + "/" + name))
}
for k in stride(from: 0, to: staves.count - 1, by: 2) {
    let top = (staves[k][0] - 70) * scale, bottom = (staves[k + 1][4] + 70) * scale
    let partW = Double(W) / 3 + 80
    for part in 0..<3 {
        let x = max(0, Double(part) * Double(W) / 3 - 40)
        let rect = CGRect(x: x, y: max(0, top), width: min(partW, Double(W) - x), height: min(bottom, Double(H)) - max(0, top))
        if let crop = full.cropping(to: rect) { save(crop, "zeile\(k / 2 + 1)_\(part + 1).png") }
    }
}
print("Ausschnitte gespeichert in \(outDir): zeile1_1.png … zeile\(staves.count / 2)_3.png")
