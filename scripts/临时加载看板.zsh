#!/bin/zsh
# 排障时一次性打开官方 App，并挂载汉化和看板。
set -e
pkg_dir="${0:A:h:h}"
app=/Applications/Antigravity.app
node_bin="$(command -v node)" || { print -u2 '终端中未找到 Node.js。'; exit 1; }
proxy_port="${1:-7897}"
if [[ "$proxy_port" != <-> ]] || (( proxy_port < 1 || proxy_port > 65535 )); then
  print -u2 '请输入有效的 Clash 端口。'
  exit 1
fi
if /usr/bin/pgrep -f '^/Applications/Antigravity\.app/Contents/MacOS/Antigravity([[:space:]]|$)' >/dev/null; then
  print -u2 '请先通过菜单退出 Antigravity。'
  exit 1
fi
proxy="http://127.0.0.1:$proxy_port"
/usr/bin/open -a "$app" --env "HTTP_PROXY=$proxy" --env "HTTPS_PROXY=$proxy" \
  --env 'NO_PROXY=localhost,127.0.0.1,::1' \
  --args "--proxy-server=$proxy" '--remote-debugging-address=127.0.0.1' '--remote-debugging-port=0'
for attempt in {1..40}; do
  if pid="$(/usr/bin/pgrep -f '^/Applications/Antigravity\.app/Contents/MacOS/Antigravity .*--remote-debugging-port=0')"; then
    exec "$node_bin" "$pkg_dir/src/load-interface.cjs" "$pid" "$pkg_dir/vendor/context-viewer"
  fi
  sleep 0.25
done
print -u2 '官方 App 的调试实例未就绪。'
exit 1
