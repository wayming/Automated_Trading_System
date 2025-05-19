fn main() {
    tonic_build::compile_protos("proto/mock_executor.proto").unwrap();
}
