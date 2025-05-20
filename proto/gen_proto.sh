# conda activate
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. trade_executor.proto

