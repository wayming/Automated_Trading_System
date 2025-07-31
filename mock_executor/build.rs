use std::env;
use std::path::PathBuf;

fn main() {
    let proto_dir = env::var("PROTO_DIR").expect("PROTO_DIR environment variable not set");
    let trade_proto = PathBuf::from(&proto_dir).join("trade_executor.proto");
    let stockhub_proto = PathBuf::from(&proto_dir).join("stock_hub.proto");

    tonic_build::configure()
        .compile(&[trade_proto, stockhub_proto], &[proto_dir])
        .expect("Failed to compile protos");

    println!("cargo:rerun-if-env-changed=PROTO_DIR");
}
