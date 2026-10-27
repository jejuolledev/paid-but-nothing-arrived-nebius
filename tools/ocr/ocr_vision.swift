// Free, on-device OCR baseline: Apple Vision VNRecognizeTextRequest (accurate, ko/ja/en).
// Usage: ocr_vision <image> [<image> ...]  -> one JSON object per line:
//   {"file": ..., "width": W, "height": H, "lines": [{"text": ..., "conf": 0.98, "box": [x0, y0, x1, y1]}]}
// box is in pixels, origin top-left. No network; macOS only.
import Foundation
import Vision
import AppKit

func ocr(_ path: String) -> [String: Any] {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        return ["file": path, "error": "cannot read image"]
    }
    let w = Double(cg.width), h = Double(cg.height)
    var lines: [[String: Any]] = []
    let req = VNRecognizeTextRequest { r, _ in
        for o in (r.results as? [VNRecognizedTextObservation]) ?? [] {
            guard let c = o.topCandidates(1).first else { continue }
            let b = o.boundingBox
            lines.append(["text": c.string, "conf": Double(c.confidence),
                          "box": [b.minX * w, (1 - b.maxY) * h, b.maxX * w, (1 - b.minY) * h]])
        }
    }
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    req.recognitionLanguages = ["ko-KR", "ja-JP", "en-US"]
    if #available(macOS 13.0, *) { req.automaticallyDetectsLanguage = false }
    do { try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req]) }
    catch { return ["file": path, "error": "\(error)"] }
    return ["file": path, "width": w, "height": h, "lines": lines]
}

for p in CommandLine.arguments.dropFirst() {
    let d = try! JSONSerialization.data(withJSONObject: ocr(p), options: [])
    print(String(data: d, encoding: .utf8)!)
}
