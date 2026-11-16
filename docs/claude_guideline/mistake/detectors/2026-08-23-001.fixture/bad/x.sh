f() {
  cmd
  local a; [ $? -eq 0 ] && a=yes || a=no
}
