import * as vscode from 'vscode';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';

let backendProcess: ChildProcess | null = null;

let lastActiveEditorPath = '';
let lastCursorLine = 0;
let lastCursorChar = 0;

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
            const strData = data.toString();
            // Uvicorn and Python logging output to stderr by default. We should only treat it as an error if it actually contains error keywords.
            if (strData.includes('ERROR') || strData.includes('Exception') || strData.includes('Traceback')) {
                console.error(`[FastAPI Error] ${strData}`);
            } else {
                console.log(`[FastAPI Log] ${strData}`);
            }
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

    if (vscode.window.activeTextEditor) {
        lastActiveEditorPath = vscode.window.activeTextEditor.document.uri.fsPath;
        lastCursorLine = vscode.window.activeTextEditor.selection.active.line + 1;
        lastCursorChar = vscode.window.activeTextEditor.selection.active.character;
    }

    // 3. 监听编辑器活动文件变化，实时发送给 Webview
    vscode.window.onDidChangeActiveTextEditor(editor => {
        if (editor) {
            lastActiveEditorPath = editor.document.uri.fsPath;
            lastCursorLine = editor.selection.active.line + 1;
            lastCursorChar = editor.selection.active.character;
            
            if (provider.view) {
                provider.view.webview.postMessage({
                    type: 'activeFileChanged',
                    filePath: lastActiveEditorPath,
                    cursorLine: lastCursorLine,
                    cursorCharacter: lastCursorChar
                });
            }
        }
    });

    vscode.window.onDidChangeTextEditorSelection(event => {
        lastActiveEditorPath = event.textEditor.document.uri.fsPath;
        lastCursorLine = event.selections[0].active.line + 1;
        lastCursorChar = event.selections[0].active.character;
        
        if (provider.view) {
            provider.view.webview.postMessage({
                type: 'cursorMoved',
                filePath: lastActiveEditorPath,
                cursorLine: lastCursorLine,
                cursorCharacter: lastCursorChar
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
                <iframe id="react-frame" src="http://localhost:12703?env=vscode" allow="clipboard-read; clipboard-write"></iframe>
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
                        // Check if it's an HTML file and open using Webview Panel
                        if (filePath.endsWith('.html')) {
                            const panel = vscode.window.createWebviewPanel(
                                'explainerPreview',
                                'Interactive Explainer',
                                vscode.ViewColumn.One,
                                { enableScripts: true }
                            );
                            const htmlContent = await vscode.workspace.fs.readFile(vscode.Uri.file(filePath));
                            panel.webview.html = htmlContent.toString();
                        } else {
                            const doc = await vscode.workspace.openTextDocument(filePath);
                            await vscode.window.showTextDocument(doc, { preview: false, viewColumn: vscode.ViewColumn.One });
                        }
                    } catch (e) {
                        vscode.window.showErrorMessage('无法打开文件: ' + filePath);
                    }
                    break;
                }
                case 'applyWorkspaceEdit': {
                    const { filePath, edits } = data;
                    const uri = vscode.Uri.file(filePath);
                    const workspaceEdit = new vscode.WorkspaceEdit();
                    
                    // edits array: [{ range: {startLine, startChar, endLine, endChar}, newText: string }]
                    for (const edit of edits) {
                        const range = new vscode.Range(
                            new vscode.Position(edit.range.startLine - 1, edit.range.startChar),
                            new vscode.Position(edit.range.endLine - 1, edit.range.endChar)
                        );
                        workspaceEdit.replace(uri, range, edit.newText);
                    }
                    
                    await vscode.workspace.applyEdit(workspaceEdit);
                    vscode.window.showInformationMessage('媚吻锋已通过法术修改了您的代码 (可 Ctrl+Z 撤销)');
                    break;
                }
                case 'runTerminalCommand': {
                    const { command } = data;
                    let terminal = vscode.window.terminals.find(t => t.name === 'MeiWenfeng Bash');
                    if (!terminal) {
                        terminal = vscode.window.createTerminal('MeiWenfeng Bash');
                    }
                    terminal.show();
                    terminal.sendText(command);
                    vscode.window.showInformationMessage('媚吻锋已帮您执行底层终端命令');
                    break;
                }
                case 'webviewReady': {
                    if (lastActiveEditorPath && this.view) {
                        this.view.webview.postMessage({
                            type: 'activeFileChanged',
                            filePath: lastActiveEditorPath,
                            cursorLine: lastCursorLine,
                            cursorCharacter: lastCursorChar
                        });
                    }
                    break;
                }
                case 'openVirtualDocument': {
                    try {
                        const doc = await vscode.workspace.openTextDocument({
                            content: data.content,
                            language: data.language || 'plaintext'
                        });
                        await vscode.window.showTextDocument(doc, { preview: false });
                    } catch (e) {
                        vscode.window.showErrorMessage('无法打开虚拟文档');
                    }
                    break;
                }
            }
        });
    }
}
