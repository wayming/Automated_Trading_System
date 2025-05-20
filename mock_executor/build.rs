use std::env;
use std::path::PathBuf;

fn main() {
    let proto_dir = env::var("PROTO_DIR").expect("PROTO_DIR environment variable not set");
    let proto_path = PathBuf::from(proto_dir).join("trade_executor.proto");

    tonic_build::compile_protos(proto_path).expect("Failed to compile proto");

    println!("cargo:rerun-if-env-changed=PROTO_DIR");
}
