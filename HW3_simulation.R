# Biostat 619 Homework 3: biased coin dose-escalation simulation
sim_biasedcoin <- function(true_probs, start = 1, q_esc = 1,
                           npat = 20, nsim = 100) {
  stopifnot(is.numeric(true_probs), length(true_probs) >= 1,
            all(is.finite(true_probs)), all(true_probs >= 0 & true_probs <= 1),
            length(start) == 1, start == as.integer(start),
            start >= 1, start <= length(true_probs),
            length(q_esc) == 1, is.finite(q_esc), q_esc >= 0, q_esc <= 1,
            length(npat) == 1, npat == as.integer(npat), npat >= 1,
            length(nsim) == 1, nsim == as.integer(nsim), nsim >= 1)
  dose_assignment <- matrix(NA_integer_, nrow = nsim, ncol = npat)
  dlt <- matrix(NA_integer_, nrow = nsim, ncol = npat)
  dose_assignment[, 1] <- start
  dlt[, 1] <- rbinom(nsim, 1, true_probs[dose_assignment[, 1]])
  if (npat > 1) {
    for (k in 2:npat) {
      # If no DLT, escalate with probability q_esc; otherwise de-escalate.
      decision <- ifelse(dlt[, k - 1] == 1, -1L,
                         rbinom(nsim, 1, q_esc))
      dose_assignment[, k] <- pmin(length(true_probs),
                                   pmax(1L, dose_assignment[, k - 1] + decision))
      dlt[, k] <- rbinom(nsim, 1, true_probs[dose_assignment[, k]])
    }
  }
  prop_at_each <- vapply(seq_along(true_probs),
                          function(j) mean(dose_assignment == j), numeric(1))
  avg_dlt_rate <- mean(dlt)
  list(prop_at_each = prop_at_each, avg_dlt_rate = avg_dlt_rate)
}

# Reset seed for each scenario to make each result independently reproducible.
for (q in c(0.25, 0.50, 1.00)) {
  set.seed(123)
  ans <- sim_biasedcoin(c(0.1, 0.2, 0.3, 0.4), start = 1,
                        q_esc = q, npat = 30, nsim = 1000)
  cat(sprintf('q_esc = %.2f\n', q))
  cat('Proportion at each dose:', sprintf('%.6f', ans$prop_at_each), '\n')
  cat('Overall DLT rate:', sprintf('%.6f', ans$avg_dlt_rate), '\n\n')
}
