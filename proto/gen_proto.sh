# conda activate
python -m grpc_tools.protoc -I. --python_out=./proto --grpc_python_out=./proto trade_executor.proto