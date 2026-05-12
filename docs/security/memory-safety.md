# Memory Safety

Python/Java reducen riesgo, pero no lo eliminan (extensiones nativas/JNI).

Si Argus incorpora código nativo:
- preferir Rust sobre C/C++
- usar ASan/MSan/Valgrind en CI de componentes nativos
