# Terraform module stubs for the AWS deployment path. This is a reference structure,
# not a click-and-deploy stack -- values like VPC CIDR, instance sizing, and account
# IDs are placeholders meant to be filled in per environment. See docs/tech-stack.md
# for why Terraform over CloudFormation/Pulumi.

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state -- never store state locally for a shared/prod environment.
  backend "s3" {
    bucket         = "REPLACE_ME-kip-terraform-state"
    key            = "kip/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "kip-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

module "networking" {
  source   = "./modules/networking"
  vpc_cidr = var.vpc_cidr
  env      = var.environment
}

module "eks" {
  source          = "./modules/eks"
  cluster_name    = "kip-${var.environment}"
  vpc_id          = module.networking.vpc_id
  subnet_ids      = module.networking.private_subnet_ids
  node_min_size   = 2
  node_max_size   = 20
  node_instance_type = "m6i.large"
}

module "rds_postgres" {
  source            = "./modules/rds"
  identifier         = "kip-${var.environment}"
  engine_version     = "16"
  instance_class     = "db.r6g.large"
  allocated_storage  = 100
  multi_az           = var.environment == "production"
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.private_subnet_ids
}

module "s3_document_storage" {
  source      = "./modules/s3"
  bucket_name = "kip-${var.environment}-documents"
  versioning  = true
  encryption  = "aws:kms"
}

module "sqs_ingestion_queue" {
  source     = "./modules/sqs"
  queue_name = "kip-${var.environment}-ingestion"
  dlq_enabled = true
  visibility_timeout_seconds = 300
}

module "elasticache_redis" {
  source     = "./modules/elasticache"
  cluster_id = "kip-${var.environment}"
  node_type  = "cache.r6g.large"
  vpc_id     = module.networking.vpc_id
  subnet_ids = module.networking.private_subnet_ids
}

module "secrets_manager" {
  source = "./modules/secrets"
  env    = var.environment
}
