// 动态判断后端地址
// 如果是通过本地 localhost 或 127.0.0.1 访问，后端地址就是本地的 12701 端口
// 如果是通过局域网 IP（例如 192.168.1.5）访问，后端地址会自动变成该局域网 IP 的 12701 端口
export const API_BASE = `http://${window.location.hostname}:12701`;
