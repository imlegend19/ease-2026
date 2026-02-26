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

pattern <- "^sk_esd_input_(fixed|reopened)_(minor|major|critical|trivial|blocker)\\.csv$"
input_files <- list.files(input_dir, pattern = pattern, full.names = TRUE)

if (length(input_files) == 0) {
  stop(sprintf("No SK-ESD input files found in: %s", input_dir), call. = FALSE)
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
    empty_df <- data.frame(
      metric = character(),
      severity = character(),
      hero_code = character(),
      rank = integer(),
      method = character()
    )
    write.csv(empty_df, output_path, row.names = FALSE, quote = FALSE)
    next
  }

  sk_result <- sk_esd(input_df)

  # Legacy mapping used in the Python pipeline:
  # result[[2]] -> rank values, result[[4]] -> column order (1-based).
  rank_values <- as.integer(unlist(sk_result[[2]]))
  column_order <- as.integer(unlist(sk_result[[4]]))
  hero_codes <- colnames(input_df)[column_order]

  if (length(rank_values) != length(hero_codes)) {
    stop(
      sprintf(
        "ScottKnottESD output mismatch for %s: %d ranks vs %d hero codes",
        file_name,
        length(rank_values),
        length(hero_codes)
      ),
      call. = FALSE
    )
  }

  ranking_df <- data.frame(
    metric = rep(metric, length(hero_codes)),
    severity = rep(severity, length(hero_codes)),
    hero_code = hero_codes,
    rank = rank_values,
    method = rep("sk_esd_docker", length(hero_codes))
  )
  write.csv(ranking_df, output_path, row.names = FALSE, quote = FALSE)
}

cat(sprintf("Generated SK-ESD rankings in %s\n", output_dir))
