// Background helper for Voice Mode:
// - stops speech the moment the microphone turns on (dictation starts)
// - Option+M toggles mute by creating/removing <data>/.mute
// - optional (`touch <data>/.dictation-key`): Option+D, or a tap on Right Shift alone, presses the
//   dictation (mic) button of the Claude desktop app, which has no shortcut of its own. Needs the
//   Accessibility permission; after a rebuild, remove and re-add mic_watch there.
//   `mic_watch --dump` lists the app's buttons.
// - optional: after dictation ends and a dictation app (e.g. Typeless) has pasted the text, presses
//   Enter in the apps below. Enabled by `touch <data>/.autosend`.
import Cocoa
import CoreAudio
import Carbon.HIToolbox
import ApplicationServices

let dataDir = NSString(string: "~/.claude/plugins/data/voice-mode").expandingTildeInPath
let muteFile = dataDir + "/.mute"
let autoSendFile = dataDir + "/.autosend"

func run(_ path: String, _ args: [String]) {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: path)
    p.arguments = args
    try? p.run()
}

func stopSpeech() {
    run("/usr/bin/pkill", ["-USR1", "-f", "kokoro_daemon.py"])
    run("/usr/bin/pkill", ["-x", "say"])
}

func toggleMute() {
    let fm = FileManager.default
    if fm.fileExists(atPath: muteFile) {
        try? fm.removeItem(atPath: muteFile)
        run("/usr/bin/afplay", ["/System/Library/Sounds/Tink.aiff"])
    } else {
        fm.createFile(atPath: muteFile, contents: nil)
        stopSpeech()
        usleep(150_000)
        run("/usr/bin/afplay", ["/System/Library/Sounds/Pop.aiff"])
    }
}

// --- Claude desktop app's dictation button, via Accessibility ---------------------------------
func axAttr(_ e: AXUIElement, _ name: String) -> Any? {
    var v: AnyObject?
    AXUIElementCopyAttributeValue(e, name as CFString, &v)
    return v
}

func axButtons(_ e: AXUIElement, _ depth: Int = 0, _ out: inout [(AXUIElement, String)]) {
    if depth > 60 || out.count > 500 { return }
    let role = axAttr(e, kAXRoleAttribute) as? String ?? ""
    if ["AXButton", "AXMenuButton", "AXPopUpButton", "AXCheckBox", "AXRadioButton", "AXSwitch", "AXToggle"].contains(role) {
        let label = [kAXTitleAttribute, kAXDescriptionAttribute, kAXHelpAttribute, kAXValueAttribute]
            .compactMap { axAttr(e, $0) as? String }.joined(separator: " | ")
        out.append((e, role + ": " + label))
    }
    if let kids = axAttr(e, kAXChildrenAttribute) as? [AXUIElement] {
        for k in kids { axButtons(k, depth + 1, &out) }
    }
}

func claudeApp() -> AXUIElement? {
    guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: "com.anthropic.claudefordesktop").first
    else { return nil }
    return AXUIElementCreateApplication(app.processIdentifier)
}

func log(_ s: String) {
    let line = "\(Date()) \(s)\n"
    if let h = FileHandle(forWritingAtPath: dataDir + "/mic_watch.log") {
        h.seekToEndOfFile(); h.write(line.data(using: .utf8)!); h.closeFile()
    } else {
        FileManager.default.createFile(atPath: dataDir + "/mic_watch.log", contents: line.data(using: .utf8))
    }
}

func pressDictation() {
    guard let app = claudeApp() else {
        log("Option+D: Claude desktop app not running")
        run("/usr/bin/afplay", ["/System/Library/Sounds/Basso.aiff"]); return
    }
    var buttons: [(AXUIElement, String)] = []
    axButtons(app, 0, &buttons)
    log("Option+D: trusted=\(AXIsProcessTrusted()) buttons=\(buttons.count)")
    // The composer's mic is a toggle (AXCheckBox) labelled "Press and hold to record" while idle and
    // differently while recording; session titles are plain buttons, so only toggles are considered.
    let wanted = try! NSRegularExpression(pattern: "^AXCheckBox:.*(record|dictat)", options: .caseInsensitive)
    if let hit = buttons.first(where: { wanted.firstMatch(in: $0.1, range: NSRange($0.1.startIndex..., in: $0.1)) != nil }) {
        AXUIElementPerformAction(hit.0, kAXPressAction as CFString)
    } else {
        run("/usr/bin/afplay", ["/System/Library/Sounds/Basso.aiff"])
    }
}

if CommandLine.arguments.contains("--dump") {
    print("accessibility trusted:", AXIsProcessTrusted())
    if let app = claudeApp() {
        var buttons: [(AXUIElement, String)] = []
        axButtons(app, 0, &buttons)
        for (_, label) in buttons { print("button:", label) }
        print(buttons.count, "buttons")
    } else {
        print("Claude desktop app not running")
    }
    exit(0)
}

func micRunning() -> Bool {
    var dev = AudioDeviceID(0)
    var size = UInt32(MemoryLayout<AudioDeviceID>.size)
    var addr = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDefaultInputDevice,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &dev) == noErr
    else { return false }
    var running: UInt32 = 0
    size = UInt32(MemoryLayout<UInt32>.size)
    addr.mSelector = kAudioDevicePropertyDeviceIsRunningSomewhere
    guard AudioObjectGetPropertyData(dev, &addr, 0, nil, &size, &running) == noErr else { return false }
    return running != 0
}

let sendApps = ["Claude", "Terminal", "iTerm2", "Ghostty", "Warp", "Code", "Cursor"]
let pasteboard = NSPasteboard.general
var wasOn = micRunning()
var micOnAt = Date()
var waitSince: Date?
var firstChangeAt: Date?
var ccBase = 0

func pressEnter() {
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
        for down in [true, false] {
            CGEvent(keyboardEventSource: nil, virtualKey: CGKeyCode(kVK_Return), keyDown: down)?
                .post(tap: .cghidEventTap)
        }
    }
}

// Option+D and the optional auto-Enter both need Accessibility; ask once at start.
_ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue(): true] as CFDictionary)

Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { _ in
    let on = micRunning()
    if on && !wasOn {
        stopSpeech()
        micOnAt = Date()
        waitSince = nil
    } else if !on && wasOn && Date().timeIntervalSince(micOnAt) > 0.8
        && FileManager.default.fileExists(atPath: autoSendFile)
        && sendApps.contains(NSWorkspace.shared.frontmostApplication?.localizedName ?? "") {
        waitSince = Date()
        firstChangeAt = nil
        ccBase = pasteboard.changeCount
    }
    wasOn = on

    // Dictation apps paste via the clipboard: set it, paste, then restore it (two changes).
    if let since = waitSince {
        let changes = pasteboard.changeCount - ccBase
        if changes >= 2 {
            pressEnter(); waitSince = nil
        } else if changes == 1 {
            if let first = firstChangeAt {
                if Date().timeIntervalSince(first) > 1.0 { pressEnter(); waitSince = nil }
            } else { firstChangeAt = Date() }
        } else if Date().timeIntervalSince(since) > 6 {
            waitSince = nil
        }
    }
}

var hotKeyRef: EventHotKeyRef?
var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
InstallEventHandler(GetApplicationEventTarget(), { _, event, _ in
    var hk = EventHotKeyID()
    GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID),
                      nil, MemoryLayout<EventHotKeyID>.size, nil, &hk)
    if hk.id == 2 { pressDictation() } else { toggleMute() }
    return noErr
}, 1, &spec, nil, nil)
RegisterEventHotKey(UInt32(kVK_ANSI_M), UInt32(optionKey),
                    EventHotKeyID(signature: OSType(0x564d4f44), id: 1),
                    GetApplicationEventTarget(), 0, &hotKeyRef)
// Optional dictation key, enabled by `touch <data>/.dictation-key`: Option+D, or a tap on Right
// Shift alone (pressed and released within half a second, no other key in between), presses the
// desktop app's mic button. Right Shift is skipped while Typeless runs, which uses the same key.
var dictateKeyRef: EventHotKeyRef?
var rightShiftDownAt: Date?
if FileManager.default.fileExists(atPath: dataDir + "/.dictation-key") {
    RegisterEventHotKey(UInt32(kVK_ANSI_D), UInt32(optionKey),
                        EventHotKeyID(signature: OSType(0x564d4f44), id: 2),
                        GetApplicationEventTarget(), 0, &dictateKeyRef)
    NSEvent.addGlobalMonitorForEvents(matching: .flagsChanged) { ev in
        guard ev.keyCode == UInt16(kVK_RightShift) else { rightShiftDownAt = nil; return }
        if ev.modifierFlags.contains(.shift) {
            rightShiftDownAt = Date()
        } else if let t = rightShiftDownAt {
            rightShiftDownAt = nil
            let typeless = NSWorkspace.shared.runningApplications.contains { $0.localizedName?.lowercased() == "typeless" }
            if Date().timeIntervalSince(t) < 0.5 && !typeless { pressDictation() }
        }
    }
    NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { _ in rightShiftDownAt = nil }
}

NSApplication.shared.setActivationPolicy(.accessory)
NSApplication.shared.run()
