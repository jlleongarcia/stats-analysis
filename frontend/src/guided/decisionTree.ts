/**
 * A small guided flow: the user answers a few questions about their goal and
 * data shape, and we recommend a test id (plus fallbacks and the reasoning).
 * The actual assumption checks run through the normal registry afterwards.
 */

export interface Question {
  id: string;
  prompt: string;
  options: { label: string; value: string; hint?: string }[];
}

export interface Recommendation {
  testId: string;
  rationale: string;
  alternatives: { testId: string; when: string }[];
  checkFirst?: { testId: string; note: string };
}

export const QUESTIONS: Question[] = [
  {
    id: "goal",
    prompt: "What do you want to find out?",
    options: [
      { label: "Compare an average across groups", value: "compare_means" },
      { label: "Compare a before/after (paired) measurement", value: "paired" },
      { label: "Relationship between two numeric variables", value: "association" },
      { label: "Relationship between two categories", value: "cat_assoc" },
      { label: "Predict a numeric outcome from predictors", value: "predict_num" },
      { label: "Predict a yes/no outcome", value: "predict_bin" },
      { label: "Just describe / check distribution", value: "describe" },
    ],
  },
  {
    id: "groups",
    prompt: "How many groups are you comparing?",
    options: [
      { label: "Two groups", value: "two" },
      { label: "Three or more", value: "many" },
    ],
  },
  {
    id: "normal",
    prompt: "Are the values roughly bell-shaped (normal) in each group?",
    options: [
      { label: "Yes / close enough", value: "yes" },
      { label: "No / skewed / small sample / not sure", value: "no" },
    ],
  },
  {
    id: "equalvar",
    prompt: "Do the groups have similar spread (variance)?",
    options: [
      { label: "Yes / not sure", value: "yes" },
      { label: "No, clearly different", value: "no" },
    ],
  },
];

/** Which questions to ask next given answers so far. */
export function nextQuestion(answers: Record<string, string>): Question | null {
  if (!answers.goal) return QUESTIONS[0];
  const g = answers.goal;
  if ((g === "compare_means") && !answers.groups) return QUESTIONS[1];
  if ((g === "compare_means" || g === "paired") && !answers.normal) return QUESTIONS[2];
  if (g === "compare_means" && answers.normal === "yes" && !answers.equalvar) return QUESTIONS[3];
  return null;
}

export function recommend(answers: Record<string, string>): Recommendation {
  const { goal, groups, normal, equalvar } = answers;

  if (goal === "describe") {
    return {
      testId: "descriptives",
      rationale: "You want a summary, not a hypothesis test.",
      alternatives: [{ testId: "shapiro_wilk", when: "you specifically need a normality verdict" }],
    };
  }

  if (goal === "association") {
    return normal === "no"
      ? {
          testId: "spearman",
          rationale: "Monotonic association without a normality assumption; robust to outliers.",
          alternatives: [
            { testId: "kendall", when: "small sample or many tied ranks" },
            { testId: "pearson", when: "the relationship is linear and both variables are ~normal" },
          ],
        }
      : {
          testId: "pearson",
          rationale: "Standard measure of linear association for numeric variables.",
          alternatives: [{ testId: "spearman", when: "the trend is monotonic but not linear" }],
        };
  }

  if (goal === "cat_assoc") {
    return {
      testId: "chi_square_independence",
      rationale: "Tests whether two categorical variables are associated.",
      alternatives: [{ testId: "fisher_exact", when: "a 2x2 table with small expected counts" }],
    };
  }

  if (goal === "predict_num") {
    return {
      testId: "linear_regression",
      rationale: "Models a numeric outcome as a linear function of one or more predictors.",
      alternatives: [{ testId: "correlation_matrix", when: "you only need pairwise strength, not a model" }],
    };
  }

  if (goal === "predict_bin") {
    return {
      testId: "logistic_regression",
      rationale: "Models the probability of a binary outcome; reports odds ratios.",
      alternatives: [],
    };
  }

  if (goal === "paired") {
    return normal === "no"
      ? {
          testId: "wilcoxon",
          rationale: "Rank-based test for two paired measurements; no normality assumption.",
          alternatives: [{ testId: "paired_t", when: "the differences look roughly normal" }],
        }
      : {
          testId: "paired_t",
          rationale: "Compares two measurements on the same units when differences are ~normal.",
          alternatives: [{ testId: "wilcoxon", when: "the differences are skewed" }],
        };
  }

  // goal === "compare_means"
  if (groups === "many") {
    if (normal === "no") {
      return {
        testId: "kruskal_wallis",
        rationale: "3+ independent groups, no normality assumption.",
        alternatives: [{ testId: "one_way_anova", when: "residuals are ~normal" }],
      };
    }
    return equalvar === "no"
      ? {
          testId: "welch_anova",
          rationale: "3+ groups with unequal variances — Welch's ANOVA is robust to that.",
          alternatives: [{ testId: "posthoc_games_howell", when: "you need pairwise follow-ups" }],
          checkFirst: { testId: "levene", note: "Confirm the variances really differ." },
        }
      : {
          testId: "one_way_anova",
          rationale: "3+ groups, approximately normal, similar spread.",
          alternatives: [{ testId: "posthoc_tukey", when: "you need pairwise follow-ups" }],
          checkFirst: { testId: "levene", note: "Check homogeneity of variance." },
        };
  }

  // two groups
  if (normal === "no") {
    return {
      testId: "mann_whitney",
      rationale: "Two independent groups, no normality assumption.",
      alternatives: [{ testId: "welch_t", when: "samples are large or clearly normal" }],
    };
  }
  return equalvar === "no"
    ? {
        testId: "welch_t",
        rationale: "Two groups, normal-ish, unequal spread — Welch's t-test is the safe default.",
        alternatives: [{ testId: "mann_whitney", when: "you'd rather not assume normality" }],
        checkFirst: { testId: "levene", note: "Confirm the spreads differ." },
      }
    : {
        testId: "student_t",
        rationale: "Two groups, normal-ish, similar spread.",
        alternatives: [{ testId: "welch_t", when: "you're unsure about equal variance (it's the safer choice)" }],
        checkFirst: { testId: "levene", note: "Check equal variance before trusting Student's t." },
      };
}
