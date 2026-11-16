f() {
  local a rc
  cmd; rc=$?
  [ "$rc" -eq 0 ] && a=yes || a=no
}
