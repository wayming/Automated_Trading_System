import grpc
import json
import logging
from concurrent import futures
import os
import requests
import sys

from proto import analysis_push_gateway_pb2 as pb2
from proto import analysis_push_gateway_pb2_grpc as pb2_grpc

HTTP_API_ENDPOINT = os.getenv("HTTP_API_ENDPOINT")

class AnalysisPushGatewayServicer(pb2_grpc.AnalysisPushGatewayServicer):
    def Push(self, request, context):
        try:
            message = request.message
            print(f"Push {message}")

            # Check if the message is a valid JSON (for logging purposes)
            try:
                # Try to parse it as JSON (if it's a valid JSON string)
                json_data = json.loads(message)
                print(f"Message is valid JSON: {json_data}")
                
                # If it's valid JSON, set content type to application/json
                headers = {'Content-Type': 'application/json'}
                
                # Send the JSON as the body of the POST request
                response = requests.post(
                    HTTP_API_ENDPOINT,
                    json=json_data,  # Use json parameter to send JSON properly
                    headers=headers
                )
            except json.JSONDecodeError:
                # If not valid JSON, treat it as plain text
                print(f"Message is plain text: {message}")
                
                # Set content type to plain text for non-JSON messages
                headers = {'Content-Type': 'text/plain'}
                response = requests.post(
                    HTTP_API_ENDPOINT,
                    data=message,  # Send as plain text
                    headers=headers
                )
        except Exception as e:
            return pb2.PushResponse(
                status_code=500,
                response_text=str(e)
            )

def serve():
    if (HTTP_API_ENDPOINT is None) :
        print("No HTTP_API_ENDPOINT")
        sys.exit(1)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_AnalysisPushGatewayServicer_to_server(AnalysisPushGatewayServicer(), server)
    server.add_insecure_port('[::]:50053')
    print("gRPC Server is running on port 50053")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
