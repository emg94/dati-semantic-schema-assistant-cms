output "agent_service_name" {
  value = google_cloud_run_v2_service.agent.name
}

output "agent_url" {
  value = google_cloud_run_v2_service.agent.uri
}

output "ingestion_job_name" {
  value = google_cloud_run_v2_job.ingestion.name
}
