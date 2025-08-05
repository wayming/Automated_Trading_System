variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "bucket_name" {
  type    = string
  default = "qts-front" # 请改为你自己的全局唯一 S3 名称
}

variable "env" {
  type    = string
  default = "prod"
}
