#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript rq3_sk_esd_docker_runner.R <input_dir> <output_dir>", call. = FALSE)
}

input_dir <- args[[1]]
output_dir <- args[[2]]

if (!dir.exists(input_dir)) {
  stop(sprintf("Input directory does not exist: %s", input_dir), call. = FALSE)
}
if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
}

options(repos = "https://cloud.r-project.org")
if (!requireNamespace("ScottKnottESD", quietly = TRUE)) {
  install.packages("ScottKnottESD")
}
suppressPackageStartupMessages(library(ScottKnottESD))

pattern <- "^sk_esd_input_(fix_rate|reopen_rate)_(blocker|critical|major|minor|trivial)\\.csv$"
input_files <- list.files(input_dir, pattern = pattern, full.names = TRUE)
if (length(input_files) == 0) {
  stop(sprintf("No SK-ESD input files found in: %s", input_dir), call. = FALSE)
}

build_empty_df <- function(metric, severity) {
  data.frame(
    metric = character(),
    severity = character(),
    hero_code = character(),
    rank = integer(),
    method = character()
  )
}

build_mean_fallback <- function(raw_df, metric, severity) {
  if (ncol(raw_df) == 0) {
    return(build_empty_df(metric, severity))
  }

  numeric_df <- suppressWarnings(data.frame(lapply(raw_df, as.numeric), check.names = FALSE))
  if (ncol(numeric_df) == 0) {
    return(build_empty_df(metric, severity))
  }

  non_empty_cols <- colSums(!is.na(numeric_df)) > 0
  numeric_df <- numeric_df[, non_empty_cols, drop = FALSE]
  if (ncol(numeric_df) == 0) {
    return(build_empty_df(metric, severity))
  }

  means <- colMeans(numeric_df, na.rm = TRUE)
  means <- means[is.finite(means)]
  if (length(means) == 0) {
    return(build_empty_df(metric, severity))
  }

  decreasing <- identical(metric, "fix_rate")
  ordered <- sort(means, decreasing = decreasing)
  hero_codes <- names(ordered)
  data.frame(
    metric = rep(metric, length(hero_codes)),
    severity = rep(severity, length(hero_codes)),
    hero_code = hero_codes,
    rank = seq_along(hero_codes),
    method = rep("mean_fallback_docker", length(hero_codes))
  )
}

for (input_path in input_files) {
  file_name <- basename(input_path)
  matches <- regexec(pattern, file_name)
  parts <- regmatches(file_name, matches)[[1]]
  metric <- parts[[2]]
  severity <- parts[[3]]

  output_path <- file.path(output_dir, sprintf("sk_esd_ranking_%s_%s.csv", metric, severity))

  input_df <- read.csv(input_path, check.names = FALSE)
  if (nrow(input_df) == 0 || ncol(input_df) == 0) {
    write.csv(build_empty_df(metric, severity), output_path, row.names = FALSE, quote = FALSE)
    next
  }

  numeric_df <- suppressWarnings(data.frame(lapply(input_df, as.numeric), check.names = FALSE))
  non_empty_cols <- colSums(!is.na(numeric_df)) > 0
  numeric_df <- numeric_df[, non_empty_cols, drop = FALSE]
  complete_df <- numeric_df[stats::complete.cases(numeric_df), , drop = FALSE]

  ranking_df <- NULL
  if (ncol(complete_df) >= 2 && nrow(complete_df) >= 2) {
    ranking_df <- tryCatch(
      {
        sk_result <- sk_esd(complete_df)
        rank_values <- as.integer(unlist(sk_result[[2]]))
        column_order <- as.integer(unlist(sk_result[[4]]))
        hero_codes <- colnames(complete_df)[column_order]

        if (length(rank_values) != length(hero_codes)) {
          stop(
            sprintf(
              "ScottKnottESD output mismatch for %s: %d ranks vs %d hero codes",
              file_name,
              length(rank_values),
              length(hero_codes)
            )
          )
        }

        data.frame(
          metric = rep(metric, length(hero_codes)),
          severity = rep(severity, length(hero_codes)),
          hero_code = hero_codes,
          rank = rank_values,
          method = rep("sk_esd_docker", length(hero_codes))
        )
      },
      error = function(e) {
        message(
          sprintf(
            "SK-ESD failed for %s (%s). Using mean fallback ranking.",
            file_name,
            conditionMessage(e)
          )
        )
        NULL
      }
    )
  }

  if (is.null(ranking_df)) {
    ranking_df <- build_mean_fallback(input_df, metric, severity)
  }

  write.csv(ranking_df, output_path, row.names = FALSE, quote = FALSE)
}

cat(sprintf("Generated SK-ESD rankings in %s\n", output_dir))
