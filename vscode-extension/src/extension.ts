import * as vscode from 'vscode';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';

let backendProcess: ChildProcess | null = null;

export function activate(context: vscode.ExtensionContext) {
    console.log('🌸 媚吻锋随身课堂插件已激活！');

    // 1. 启动后台 FastAPI 服务
    const backendDir = path.join(context.extensionPath, '..', 'backend');
    
    // 如果系统里有 python，则尝试启动 main.py
    try {
        backendProcess = spawn('python', ['main.py'], {
            cwd: backendDir,
            shell: true
        });

        backendProcess.stdout?.on('data', (data) => {
            console.log(`[FastAPI] ${data}`);
        });

        backendProcess.stderr?.on('data', (data) => {
            console.error(`[FastAPI Error] ${data}`);
        });
        
        vscode.window.showInformationMessage('🌸 媚吻锋已苏醒 (FastAPI Backend Started)');
    } catch (e) {
        vscode.window.showErrorMessage('无法启动后台服务，请确保已安装 Python 环境。');
    }

    // 2. 注册 Webview 侧边栏
    const provider = new SidebarProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider("mei-wenfeng-sidebar", provider)
    );

    // 3. 监听编辑器活动文件变化，实时发送给 Webview
    vscode.window.onDidChangeActiveTextEditor(editor => {
        if (editor && provider.view) {
            provider.view.webview.postMessage({
                type: 'activeFileChanged',
                filePath: editor.document.uri.fsPath
            });
        }
    });
}

export function deactivate() {
    if (backendProcess) {
        backendProcess.kill();
    }
}

class SidebarProvider implements vscode.WebviewViewProvider {
    public view?: vscode.WebviewView;

    constructor(private readonly _extensionUri: vscode.Uri) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this.view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        // 为了开发方便，我们这里直接指向 Vite 本地调试服务器 (需先执行 npm run dev)
        // 生产环境时应替换为读取本地 dist/index.html 的方式
        webviewView.webview.html = `
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body, html { margin: 0; padding: 0; width: 100%; height: 100vh; overflow: hidden; }
                    iframe { width: 100%; height: 100%; border: none; }
                </style>
            </head>
            <body>
                <iframe id="react-frame" src="http://localhost:5173?env=vscode" allow="clipboard-read; clipboard-write"></iframe>
                <script>
                    const vscode = acquireVsCodeApi();
                    const iframe = document.getElementById('react-frame');
                    
                    // Forward messages from VS Code to Iframe
                    window.addEventListener('message', event => {
                        iframe.contentWindow.postMessage(event.data, '*');
                    });
                    
                    // Forward messages from Iframe to VS Code
                    window.addEventListener('message', event => {
                        if(event.source === iframe.contentWindow) {
                            vscode.postMessage(event.data);
                        }
                    });
                </script>
            </body>
            </html>
        `;

        // 接收来自前端的消息（例如：前端收到了 [SYSTEM_PASS] 或者 explainer，需要原生编辑器打开某个文件）
        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.type) {
                case 'openExplainer': {
                    const filePath = data.filePath;
                    try {
                        const doc = await vscode.workspace.openTextDocument(filePath);
                        await vscode.window.showTextDocument(doc, { preview: false, viewColumn: vscode.ViewColumn.One });
                    } catch (e) {
                        vscode.window.showErrorMessage('无法打开玉简文件: ' + filePath);
                    }
                    break;
                }
            }
        });
    }
}
