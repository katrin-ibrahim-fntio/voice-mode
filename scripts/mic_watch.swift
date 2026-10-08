// Background helper for Voice Mode:
// - stops speech the moment the microphone turns on (dictation starts)
// - Option+M toggles mute by creating/removing <data>/.mute
// - optional: after dictation ends and a dictation app (e.g. Typeless) has pasted the text, presses
//   Enter in the apps below. Enabled by `touch <data>/.autosend`; needs the Accessibility permission.
import Cocoa
import CoreAudio
import Carbon.HIToolbox

let dataDir = ProcessInfo.processInfo.environment["CLAUDE_PLUGIN_DATA"]
    ?? NSString(string: "~/.claude/plugins/data/voice-mode").expandingTildeInPath
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

if FileManager.default.fileExists(atPath: autoSendFile) {
    _ = AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue(): true] as CFDictionary)
}

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
InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
    toggleMute()
    return noErr
}, 1, &spec, nil, nil)
RegisterEventHotKey(UInt32(kVK_ANSI_M), UInt32(optionKey),
                    EventHotKeyID(signature: OSType(0x564d4f44), id: 1),
                    GetApplicationEventTarget(), 0, &hotKeyRef)

NSApplication.shared.setActivationPolicy(.accessory)
NSApplication.shared.run()
