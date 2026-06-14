"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/extension.ts
var extension_exports = {};
__export(extension_exports, {
  activate: () => activate,
  deactivate: () => deactivate
});
module.exports = __toCommonJS(extension_exports);
var vscode = __toESM(require("vscode"));
var import_child_process = require("child_process");
var path = __toESM(require("path"));
var backendProcess = null;
function activate(context) {
  console.log("\u{1F338} \u5A9A\u543B\u950B\u968F\u8EAB\u8BFE\u5802\u63D2\u4EF6\u5DF2\u6FC0\u6D3B\uFF01");
  const backendDir = path.join(context.extensionPath, "..", "backend");
  try {
    backendProcess = (0, import_child_process.spawn)("python", ["main.py"], {
      cwd: backendDir,
      shell: true
    });
    backendProcess.stdout?.on("data", (data) => {
      console.log(`[FastAPI] ${data}`);
    });
    backendProcess.stderr?.on("data", (data) => {
      console.error(`[FastAPI Error] ${data}`);
    });
    vscode.window.showInformationMessage("\u{1F338} \u5A9A\u543B\u950B\u5DF2\u82CF\u9192 (FastAPI Backend Started)");
  } catch (e) {
    vscode.window.showErrorMessage("\u65E0\u6CD5\u542F\u52A8\u540E\u53F0\u670D\u52A1\uFF0C\u8BF7\u786E\u4FDD\u5DF2\u5B89\u88C5 Python \u73AF\u5883\u3002");
  }
  const provider = new SidebarProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("mei-wenfeng-sidebar", provider)
  );
  vscode.window.onDidChangeActiveTextEditor((editor) => {
    if (editor && provider.view) {
      provider.view.webview.postMessage({
        type: "activeFileChanged",
        filePath: editor.document.uri.fsPath,
        cursorLine: editor.selection.active.line + 1,
        cursorCharacter: editor.selection.active.character
      });
    }
  });
  vscode.window.onDidChangeTextEditorSelection((event) => {
    if (provider.view) {
      provider.view.webview.postMessage({
        type: "cursorMoved",
        filePath: event.textEditor.document.uri.fsPath,
        cursorLine: event.selections[0].active.line + 1,
        cursorCharacter: event.selections[0].active.character
      });
    }
  });
}
function deactivate() {
  if (backendProcess) {
    backendProcess.kill();
  }
}
var SidebarProvider = class {
  constructor(_extensionUri) {
    this._extensionUri = _extensionUri;
  }
  resolveWebviewView(webviewView, context, _token) {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };
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
    webviewView.webview.onDidReceiveMessage(async (data) => {
      switch (data.type) {
        case "openExplainer": {
          const filePath = data.filePath;
          try {
            if (filePath.endsWith(".html")) {
              const panel = vscode.window.createWebviewPanel(
                "explainerPreview",
                "Interactive Explainer",
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
            vscode.window.showErrorMessage("\u65E0\u6CD5\u6253\u5F00\u6587\u4EF6: " + filePath);
          }
          break;
        }
        case "applyWorkspaceEdit": {
          const { filePath, edits } = data;
          const uri = vscode.Uri.file(filePath);
          const workspaceEdit = new vscode.WorkspaceEdit();
          for (const edit of edits) {
            const range = new vscode.Range(
              new vscode.Position(edit.range.startLine - 1, edit.range.startChar),
              new vscode.Position(edit.range.endLine - 1, edit.range.endChar)
            );
            workspaceEdit.replace(uri, range, edit.newText);
          }
          await vscode.workspace.applyEdit(workspaceEdit);
          vscode.window.showInformationMessage("\u5A9A\u543B\u950B\u5DF2\u901A\u8FC7\u6CD5\u672F\u4FEE\u6539\u4E86\u60A8\u7684\u4EE3\u7801 (\u53EF Ctrl+Z \u64A4\u9500)");
          break;
        }
        case "runTerminalCommand": {
          const { command } = data;
          let terminal = vscode.window.terminals.find((t) => t.name === "MeiWenfeng Bash");
          if (!terminal) {
            terminal = vscode.window.createTerminal("MeiWenfeng Bash");
          }
          terminal.show();
          terminal.sendText(command);
          vscode.window.showInformationMessage("\u5A9A\u543B\u950B\u5DF2\u5E2E\u60A8\u6267\u884C\u5E95\u5C42\u7EC8\u7AEF\u547D\u4EE4");
          break;
        }
        case "webviewReady": {
          const activeEditor = vscode.window.activeTextEditor;
          if (activeEditor && this.view) {
            this.view.webview.postMessage({
              type: "activeFileChanged",
              filePath: activeEditor.document.uri.fsPath,
              cursorLine: activeEditor.selection.active.line + 1,
              cursorCharacter: activeEditor.selection.active.character
            });
          }
          break;
        }
      }
    });
  }
};
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  activate,
  deactivate
});
