import AppKit

final class AntigravityLauncher {
    private let workspace = NSWorkspace.shared
    private let appURL = URL(fileURLWithPath: "/Applications/Antigravity.app")
    private let viewerDirectory: String
    private let loaderPath: String
    private let nodePath: String
    private var pendingQuit: pid_t?
    private var observers: [NSObjectProtocol] = []

    init(viewerDirectory: String, loaderPath: String, nodePath: String) {
        self.viewerDirectory = viewerDirectory
        self.loaderPath = loaderPath
        self.nodePath = nodePath
    }

    private func target(from notification: Notification) -> NSRunningApplication? {
        guard let app = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication,
              app.bundleIdentifier == "com.google.antigravity",
              app.bundleURL?.path == appURL.path else { return nil }
        return app
    }

    private func launchCommand(for pid: pid_t) -> String? {
        let result = Pipe()
        let ps = Process()
        ps.executableURL = URL(fileURLWithPath: "/bin/ps")
        ps.arguments = ["-ww", "-p", String(pid), "-o", "command="]
        ps.standardOutput = result
        do { try ps.run() } catch { return nil }
        let data = result.fileHandleForReading.readDataToEndOfFile()
        ps.waitUntilExit()
        guard ps.terminationStatus == 0 else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func didLaunch(_ notification: Notification) {
        guard pendingQuit == nil, let app = target(from: notification),
              let command = launchCommand(for: app.processIdentifier),
              !command.contains("--remote-debugging-port") else { return }

        // shortcut: 仅在已实测的 2.34.0 上自动重启，升级后先验证界面兼容性再放开版本。
        guard Bundle(url: appURL)?.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String == "2.34.0" else { return }

        let pid = app.processIdentifier
        pendingQuit = pid
        print("收到官方图标启动，准备正常退出一次，进程 \(pid)。")
        guard app.terminate() else {
            pendingQuit = nil
            print("应用未接受正常退出请求，本次保留原窗口。")
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) { [weak self] in
            guard let self, self.pendingQuit == pid else { return }
            self.pendingQuit = nil
            print("等待退出超时，本次保留原窗口。")
        }
    }

    private func didTerminate(_ notification: Notification) {
        guard let app = target(from: notification), pendingQuit == app.processIdentifier else { return }
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.arguments = ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0"]
        workspace.openApplication(at: appURL, configuration: configuration) { [weak self] instance, error in
            DispatchQueue.main.async {
                guard let self else { return }
                self.pendingQuit = nil
                guard let instance, error == nil else {
                    print("官方应用重新打开失败。")
                    return
                }
                self.loadEnhancements(process: instance.processIdentifier)
            }
        }
    }

    private func loadEnhancements(process pid: pid_t) {
        let loader = Process()
        loader.executableURL = URL(fileURLWithPath: nodePath)
        loader.arguments = [loaderPath, String(pid), viewerDirectory]
        do {
            try loader.run()
            print("已重开同一个官方应用，进程 \(pid)。")
        } catch {
            print("官方应用已打开，增强加载进程未能启动。")
        }
    }

    func run() {
        let notifications = workspace.notificationCenter
        observers.append(notifications.addObserver(forName: NSWorkspace.didLaunchApplicationNotification, object: nil, queue: .main) { [weak self] in self?.didLaunch($0) })
        observers.append(notifications.addObserver(forName: NSWorkspace.didTerminateApplicationNotification, object: nil, queue: .main) { [weak self] in self?.didTerminate($0) })
        print("已监听官方 Antigravity 启动。")
        RunLoop.main.run()
    }
}

guard CommandLine.arguments.count == 4 else { exit(64) }
setbuf(stdout, nil)
let launcher = AntigravityLauncher(
    viewerDirectory: CommandLine.arguments[1],
    loaderPath: CommandLine.arguments[2],
    nodePath: CommandLine.arguments[3]
)
withExtendedLifetime(launcher) { launcher.run() }
