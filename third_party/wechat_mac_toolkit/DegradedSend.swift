// Explicit user-selected Mac prototype mode. No screenshot or draft assurance.
import Cocoa
import ApplicationServices

func axWindowFrame(_ window:AXUIElement) throws -> CGRect {
    guard let p = axAttribute(window,kAXPositionAttribute as CFString),
          let s = axAttribute(window,kAXSizeAttribute as CFString),
          CFGetTypeID(p) == AXValueGetTypeID(),CFGetTypeID(s) == AXValueGetTypeID() else { throw fail("target_window_geometry_unavailable") }
    var point = CGPoint.zero,size = CGSize.zero
    guard AXValueGetValue(p as! AXValue,.cgPoint,&point),AXValueGetValue(s as! AXValue,.cgSize,&size) else { throw fail("target_window_geometry_unavailable") }
    return CGRect(origin:point,size:size)
}
func requireFocusedTarget(_ pid:pid_t,window:AXUIElement,frame:CGRect) throws {
    try requireFrontmost(pid)
    try requireNoAccountSecurityNotice(pid)
    let (_,_,current) = try boundMainWindow(calibrated:true)
    guard CFEqual(current,window),try axWindowFrame(current) == frame,
          let focused = axAttribute(AXUIElementCreateApplication(pid),kAXFocusedWindowAttribute as CFString),
          CFEqual(focused,current),
          axAttribute(current,kAXModalAttribute as CFString) as? Bool != true,
          !(axAttribute(current,kAXChildrenAttribute as CFString) as? [AXUIElement] ?? []).contains(where: {
              axAttribute($0,kAXRoleAttribute as CFString) as? String == kAXSheetRole
          }) else { throw fail("target_window_focus_or_geometry_changed") }
}
func sendWithoutCapture(chat:String,text:String,id:String,top:Double,key:String,dry:Bool) async throws {
    guard try windowMode() == .independent else { throw fail("degraded_requires_independent_window") }
    let (pid,_,window) = try boundMainWindow(calibrated:true)
    let frame = try axWindowFrame(window)
    try requireFocusedTarget(pid,window:window,frame:frame)
    let journal = try Journal(directory:option("--state-dir",".wechat-ui-state"),id:id,signature:digest(chat+"\0"+text+"\0ax-window-db"))
    guard try journal.existing() == nil else { throw fail("id_already_attempted; never_retry") }
    if dry {
        emit(["type":"send_preflight_ok","dry_run":true,"preflight":"ax-window-db",
              "draft_verified":false,"occlusion_verified":false,"input_events":0]); return
    }
    try journal.save("prepared")
    try clickPoint(CGPoint(x:frame.midX,y:frame.minY+frame.height*top+30))
    try await Task.sleep(for:.milliseconds(100))
    try requireFocusedTarget(pid,window:window,frame:frame)
    let clipboard = try ClipboardLease()
    defer { emit(["type":"clipboard_cleanup","status":clipboard.restore()]) }
    try pasteOnce(text,pid:pid,clipboard:clipboard)
    try await Task.sleep(for:.milliseconds(300))
    try requireFocusedTarget(pid,window:window,frame:frame)
    guard clipboard.pasteboard.changeCount == clipboard.installedChange else { throw fail("clipboard_changed_before_send") }
    try journal.save("dispatching")
    try enter(pid,command:key == "cmd-enter")
    try journal.save("key_dispatched")
    emit(["type":"native_input_dispatched","preflight":"ax-window-db",
          "draft_verified":false,"delivery_receipt":false,"paste_count":1,"send_key_count":1])
}
