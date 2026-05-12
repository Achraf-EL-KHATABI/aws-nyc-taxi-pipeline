# ============================================
# SNS TOPIC — pipeline notifications (success/failure)
# ============================================
resource "aws_sns_topic" "pipeline_notifications" {
  name = "${var.project_name}-pipeline-notifications"
}

# Email subscription — replace with your email
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.pipeline_notifications.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# ============================================
# IAM ROLE — for the Step Functions state machine
# ============================================
data "aws_iam_policy_document" "sfn_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "step_functions" {
  name               = "${var.project_name}-sfn-role"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume_role.json
}

# Custom policy: Step Functions can call Glue crawlers/jobs and publish to SNS
data "aws_iam_policy_document" "sfn_policy" {
  statement {
    sid = "GlueCrawlerControl"
    actions = [
      "glue:StartCrawler",
      "glue:GetCrawler",
    ]
    resources = [
      aws_glue_crawler.raw_taxi.arn,
      aws_glue_crawler.curated_taxi.arn,
    ]
  }

  statement {
    sid = "GlueJobControl"
    actions = [
      "glue:StartJobRun",
      "glue:GetJobRun",
      "glue:GetJobRuns",
      "glue:BatchStopJobRun",
    ]
    resources = [
      aws_glue_job.transform_taxi.arn,
    ]
  }

  # Glue's startJobRun.sync uses managed rules behind the scenes
  statement {
    sid = "EventsForSyncIntegration"
    actions = [
      "events:PutTargets",
      "events:PutRule",
      "events:DescribeRule",
    ]
    resources = [
      "arn:aws:events:${var.aws_region}:*:rule/StepFunctionsGetEventsForGlueJobRule",
    ]
  }

  statement {
    sid       = "SNSPublish"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.pipeline_notifications.arn]
  }

  statement {
    sid = "CloudWatchLogs"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "step_functions" {
  name   = "${var.project_name}-sfn-policy"
  role   = aws_iam_role.step_functions.id
  policy = data.aws_iam_policy_document.sfn_policy.json
}

# ============================================
# CLOUDWATCH LOGS — for state machine execution history
# ============================================
resource "aws_cloudwatch_log_group" "state_machine" {
  name              = "/aws/vendedlogs/states/${var.project_name}-pipeline"
  retention_in_days = 7
}

# ============================================
# STATE MACHINE
# ============================================
resource "aws_sfn_state_machine" "taxi_pipeline" {
  name     = "${var.project_name}-pipeline"
  role_arn = aws_iam_role.step_functions.arn
  type     = "STANDARD"

  definition = templatefile("${path.module}/../state_machine/taxi_pipeline.asl.json", {
    raw_crawler_name     = aws_glue_crawler.raw_taxi.name
    curated_crawler_name = aws_glue_crawler.curated_taxi.name
    glue_job_name        = aws_glue_job.transform_taxi.name
    sns_topic_arn        = aws_sns_topic.pipeline_notifications.arn
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.state_machine.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }
}

# ============================================
# EVENTBRIDGE SCHEDULER — daily trigger
# ============================================
data "aws_iam_policy_document" "scheduler_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.project_name}-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume_role.json
}

data "aws_iam_policy_document" "scheduler_policy" {
  statement {
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.taxi_pipeline.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "${var.project_name}-scheduler-policy"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler_policy.json
}

resource "aws_scheduler_schedule" "daily_pipeline" {
  name        = "${var.project_name}-daily-pipeline"
  description = "Daily trigger of the NYC Taxi pipeline"

  # Disabled by default — enable manually after first successful test run
  state = "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  # Daily at 03:00 Paris time
  schedule_expression          = "cron(0 3 * * ? *)"
  schedule_expression_timezone = "Europe/Paris"

  target {
    arn      = aws_sfn_state_machine.taxi_pipeline.arn
    role_arn = aws_iam_role.scheduler.arn

    input = jsonencode({
      source = "eventbridge-scheduler"
    })

    retry_policy {
      maximum_retry_attempts = 2
    }
  }
}