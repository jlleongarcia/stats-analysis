# Statistical methods

What each family of tests does, the statistic behind it, and how to read the result. For the
exact variables and settings each test takes, see the **Test reference**, which is generated from
the app itself.

Throughout: $n$ is a sample size, $\bar{x}$ a sample mean, $s$ a sample standard deviation,
$\alpha$ the significance level (0.05 unless you change it), and $p$ the p-value.

---

## Reading any result

Every test in this app returns the same shape, so once you can read one you can read all of them.

**The p-value** is the probability of seeing data at least as extreme as yours *if the null
hypothesis were true*. It is not the probability that the null is true, and it is not a measure of
effect size. A small $p$ with a trivial effect usually means a large sample; a large $p$ with a
big effect usually means a small one.

**The effect size** is the part that answers "does this matter?". Cohen's conventional
benchmarks — small/medium/large — are shown as a label, but they are conventions, not laws of
nature. Judge against what matters in your field.

**Confidence intervals** carry more information than a p-value: they show the range of effects
your data is compatible with. A 95% interval that includes zero corresponds to $p > 0.05$, but it
also tells you how big the effect might plausibly be.

**Assumption checks** appear with a green, amber or grey marker. Amber does not mean the result is
void — it means you should think about robustness, and often there is a rank-based alternative one
click away.

---

## Descriptive statistics

Always start here. Counts, missingness, central tendency, spread, quantiles, shape, and a 95%
confidence interval for the mean:

$$\bar{x} \pm t_{\alpha/2,\;n-1}\,\frac{s}{\sqrt{n}}$$

Skewness measures asymmetry and kurtosis measures tail weight; both are reported as excess over
the normal, so $0$ is normal-shaped. Values beyond about $\pm 1$ are worth a look at the
histogram before running anything parametric.

Splitting by a grouping column gives the same statistics per level, which is usually the fastest
way to see whether a formal comparison is even worth running.

---

## Normality

Most parametric tests assume approximate normality — strictly, of the *residuals* or the sampling
distribution, not the raw data. These four tests ask whether a sample is plausibly normal.

| Test | Best for | Note |
|---|---|---|
| **Shapiro-Wilk** | $n < 5000$ | The best general-purpose power; the default choice |
| **D'Agostino-Pearson** | $n \ge 8$ | Combines skewness and kurtosis into one omnibus statistic |
| **Kolmogorov-Smirnov** | any $n$ | Conservative when the mean and SD are estimated from the sample |
| **Anderson-Darling** | any $n$ | Weights the tails more heavily |

Shapiro-Wilk computes

$$W = \frac{\left(\sum_{i=1}^{n} a_i x_{(i)}\right)^2}{\sum_{i=1}^{n}(x_i - \bar{x})^2}$$

where $x_{(i)}$ are the ordered values and $a_i$ are constants from the expected normal order
statistics. $W$ near 1 means normal-looking.

**The trap.** These tests are sensitive to sample size, not to how much non-normality matters.
At $n = 5000$ a trivial deviation returns $p < 0.001$; at $n = 10$ a serious one passes. Use them
alongside a histogram and a Q-Q plot, and remember the central limit theorem: means of large
samples are near-normal even when the data is not.

---

## Comparing one or two means

### One-sample t-test
Is the mean different from a reference value $\mu_0$?

$$t = \frac{\bar{x} - \mu_0}{s/\sqrt{n}}, \qquad df = n - 1$$

### Welch's t-test — the safe default for two groups
Does not assume the groups share a variance:

$$t = \frac{\bar{x}_1 - \bar{x}_2}{\sqrt{\dfrac{s_1^2}{n_1} + \dfrac{s_2^2}{n_2}}}$$

with the Welch–Satterthwaite degrees of freedom. **Prefer this over Student's t.** It costs almost
nothing when variances are equal and protects you when they are not, which you can rarely rule
out. Student's t is provided for when you specifically need the pooled-variance version.

### Paired t-test
For two measurements on the same units. It is a one-sample t-test on the differences, which is why
it is so much more powerful than treating the two columns as independent groups — the
between-subject variation cancels out.

### Effect size
Cohen's $d$ expresses the difference in standard deviations:

$$d = \frac{\bar{x}_1 - \bar{x}_2}{s_{\text{pooled}}}$$

Conventionally 0.2 small, 0.5 medium, 0.8 large.

---

## Nonparametric alternatives

When normality is doubtful or the data is ordinal, these compare ranks instead of means. They test
whether one group tends to produce larger values, not whether means differ.

| Parametric | Nonparametric | Compares |
|---|---|---|
| Welch's / Student's t | **Mann-Whitney U** | Two independent groups |
| Paired t | **Wilcoxon signed-rank** | Two paired measurements |
| One-way ANOVA | **Kruskal-Wallis H** | Three or more independent groups |
| Repeated-measures ANOVA | **Friedman** | Three or more paired measurements |

Mann-Whitney's statistic counts how often a value from one group exceeds one from the other:

$$U_1 = R_1 - \frac{n_1(n_1+1)}{2}$$

where $R_1$ is the sum of ranks in group 1.

The cost is power — roughly 5% less than a t-test when the data really is normal — which is a
small price when you are not sure. The cost is interpretive too: a significant result means the
distributions differ in location, which is only a statement about medians if their shapes match.

---

## ANOVA

### One-way
Partitions total variation into between-group and within-group parts:

$$F = \frac{MS_{\text{between}}}{MS_{\text{within}}} = \frac{SS_{\text{between}}/(k-1)}{SS_{\text{within}}/(N-k)}$$

A significant $F$ says *some* group differs — not which. Follow it with a post-hoc test.

### Welch's ANOVA
The unequal-variance version, and the better default for the same reason Welch's t is: real groups
rarely share a variance exactly, and the classic $F$ is not robust to that when group sizes differ.

### Two-way
Two factors at once, giving main effects for each plus their **interaction**. The interaction is
usually the interesting term: it asks whether the effect of one factor depends on the level of the
other. When it is significant, interpret the main effects with care — an "average" effect across
levels may describe no one.

### Repeated measures
For the same units measured under several conditions. Removes between-subject variation, which
makes it far more powerful — but it assumes **sphericity** (equal variances of all pairwise
differences). Violations inflate the false-positive rate.

### ANCOVA
One-way ANOVA with continuous covariates partialled out; compares adjusted means. Assumes the
covariate's slope is the same in every group.

### Effect size
$$\eta^2 = \frac{SS_{\text{effect}}}{SS_{\text{total}}}$$

the proportion of variance explained. Conventionally 0.01 small, 0.06 medium, 0.14 large.

### Post-hoc tests
Comparing every pair inflates the family-wise error rate; these control it.

- **Tukey HSD** — all pairwise comparisons, assumes equal variances.
- **Games-Howell** — the same, without that assumption. Pair it with Welch's ANOVA.

---

## Correlation

| Test | Measures | Use when |
|---|---|---|
| **Pearson** $r$ | Linear association | Both variables roughly normal, the relationship is linear |
| **Spearman** $\rho$ | Monotonic association | Ranks, outliers, or a curved but consistently increasing relationship |
| **Kendall** $\tau$ | Concordance of pairs | Small samples or many ties; more interpretable than $\rho$ |

$$r = \frac{\sum (x_i - \bar{x})(y_i - \bar{y})}{\sqrt{\sum (x_i-\bar{x})^2 \sum (y_i-\bar{y})^2}}$$

$r^2$ is the shared variance — $r = 0.5$ means 25% of the variance is shared, which is less
impressive than $r$ alone sounds.

**Always plot it.** Anscombe's quartet is four datasets with identical $r$ and wildly different
shapes. A correlation matrix over many columns is useful for screening, but the number of pairs
grows as $k(k-1)/2$, so some will look significant by chance alone.

---

## Regression

### Linear (OLS)
Fits $\hat{y} = \beta_0 + \beta_1 x_1 + \dots + \beta_k x_k$ by minimising the sum of squared
residuals. Each coefficient is the expected change in $y$ per unit of that predictor **holding
the others fixed** — that conditional clause is what makes multiple regression useful and what
makes it easy to misread.

$R^2$ is the proportion of variance explained; adjusted $R^2$ penalises extra predictors and is
the one to quote when comparing models of different size.

Assumes linearity, independent errors, constant residual variance, and roughly normal residuals.
Check the residual plot before trusting anything else.

### Logistic
For a binary outcome, models the log-odds:

$$\log\!\left(\frac{p}{1-p}\right) = \beta_0 + \beta_1 x_1 + \dots + \beta_k x_k$$

Coefficients are log-odds; exponentiate for an **odds ratio**, which is what to report. An odds
ratio of 2 means the odds double per unit — not the probability, which is a common and consequential
misreading.

---

## Categorical data

### Chi-square test of independence
Are two categorical variables related?

$$\chi^2 = \sum \frac{(O - E)^2}{E}, \qquad E_{ij} = \frac{R_i C_j}{N}$$

Needs expected counts of about 5 or more in most cells; below that, use Fisher's exact test.

### Chi-square goodness of fit
Compares one variable's observed counts against expected proportions.

### Fisher's exact test
For 2×2 tables, computes the exact hypergeometric probability rather than approximating it. Always
valid, and the right choice for small samples.

### McNemar's test
For **paired** binary data — the same subjects before and after. It looks only at the discordant
cells, because the agreements carry no information about change:

$$\chi^2 = \frac{(b - c)^2}{b + c}$$

### Effect size
Cramér's V scales $\chi^2$ to a 0–1 range:

$$V = \sqrt{\frac{\chi^2}{N \cdot \min(r-1,\,c-1)}}$$

---

## Homogeneity of variance

| Test | Robustness |
|---|---|
| **Levene** | Uses absolute deviations from the group mean or median; robust to non-normality |
| **Bartlett** | More powerful when the data really is normal; very sensitive when it is not |

Use Levene unless you are confident about normality. A significant result means the groups do not
share a spread — which is an argument for Welch's t or Welch's ANOVA, not for abandoning the
comparison.

---

## Multivariate methods

### Principal component analysis
Rotates correlated variables into uncorrelated components ordered by variance explained. The first
component is the direction of greatest spread. Use it to compress many variables, to visualise
structure, or to remove collinearity before regression.

Components are eigenvectors of the correlation matrix; their eigenvalues are the variance each
explains. Keep components by the scree plot's elbow, or by eigenvalue > 1 on standardised data.
**PCA describes variance, not meaning** — a component is a mathematical axis, and whether it
corresponds to anything real is your judgement.

### Factor analysis
Superficially similar, fundamentally different in intent. PCA summarises observed variance; factor
analysis posits **latent variables** that cause the observed correlations, and models only shared
variance. Use PCA to reduce, factor analysis to hypothesise structure.

### Canonical correlation
Finds the linear combination of one set of variables that correlates most strongly with a linear
combination of another set. A correlation between two *blocks* of variables.

### Correspondence analysis
PCA's counterpart for contingency tables: maps rows and columns of a cross-tabulation into a
shared low-dimensional space, so categories that occur together sit close.

### Multidimensional scaling
Given distances between cases, places them in two dimensions so those distances are preserved as
well as possible. Useful when a similarity matrix is more natural than raw variables.

---

## Clustering

Both methods find groups without being told the answer — which means they will always return
groups, whether or not any exist. Validate before believing.

### Hierarchical
Builds a nested tree by repeatedly merging the closest pair. Ward's linkage minimises the increase
in within-cluster variance and tends to produce compact, similar-sized clusters. Read the
dendrogram and cut where the merge distances jump.

### K-means
Partitions into $k$ clusters by minimising within-cluster sum of squares:

$$\underset{S}{\arg\min} \sum_{i=1}^{k} \sum_{x \in S_i} \lVert x - \mu_i \rVert^2$$

You must choose $k$ in advance; the elbow of the inertia curve and the silhouette score both help.
K-means assumes roughly spherical, similar-sized clusters and is scale-sensitive — **standardise
first**, or the variable with the largest units will dominate.

---

## Classification

### Discriminant analysis
Finds the axes that best separate known groups, then classifies cases along them. Linear
discriminant analysis assumes the groups share a covariance matrix. It is the supervised mirror of
PCA: PCA maximises variance, LDA maximises between-group separation relative to within-group
spread.

**General discriminant analysis** adds covariates to adjust for before separating.

### Classification tree
Recursively splits on the predictor that best purifies the groups (by Gini impurity or entropy).
Trees are wonderfully interpretable and notoriously unstable: a small data change can restructure
the whole tree, and deep trees memorise the training data. Judge on held-out accuracy, not
resubstitution accuracy.

---

## Reliability

Cronbach's $\alpha$ asks whether several items measure one construct consistently:

$$\alpha = \frac{k}{k-1}\left(1 - \frac{\sum_{i=1}^{k} s_i^2}{s_T^2}\right)$$

Conventionally $\alpha \ge 0.7$ is acceptable and $\ge 0.8$ good. Two caveats worth more than the
threshold: $\alpha$ rises with the number of items regardless of quality, and a *very* high
$\alpha$ (> 0.95) usually means items are redundant rather than excellent. The item-total
statistics matter more — they show which item, if dropped, would improve the scale.

---

## Statistical process control

The one family here concerned with **time order**. Everything above is cross-sectional: compare
these groups, model this relationship. SPC asks whether a process is stable over time and capable
of meeting its specification.

It has its own two documents — the **SPC user guide** for running a study, and **SPC methodology**
for control limit formulas, the four rules, the Phase I workflow and capability indices.

---

## A note on multiple testing

Running twenty tests at $\alpha = 0.05$ gives roughly a 64% chance of at least one false positive:

$$P(\text{at least one}) = 1 - (1 - 0.05)^{20} \approx 0.64$$

This app does not correct across tests you choose to run — it cannot know which belong to one
family of hypotheses. Post-hoc tests correct within themselves; everything else is on you. Decide
what you are testing before you look, and treat anything found by exploration as a hypothesis to
confirm on new data, not as a result.
