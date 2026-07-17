# Task 2 - Ethical AI Scenario

## The Sepsis Model That Missed Two-Thirds of Cases

### The Case

Hundreds of U.S. hospitals used Epic's AI model to warn doctors when a patient might be developing sepsis, a fast-moving, deadly condition where early detection saves lives. It was deployed widely based only on the vendor's own claims. But when researchers finally ran an independent test on ~38,000 hospitalizations, it failed badly in both ways:

- **Low recall** — out of all patients who actually had sepsis, the model caught only about a third. It missed **67% of real cases** — sick patients who got no warning.
- **Low precision** — of all the patients it alarmed on (**18% of everyone**), most did not have sepsis. Too many false alarms, so doctors got "alert fatigue" and started ignoring it.

### The Ethical Challenge

This isn't bias or privacy — it's a **trusted-but-untested black-box model doing quiet harm**. It missed the people who needed help most (dangerous false negatives) while flooding staff with false alarms (false positives). The core failure was **governance and transparency**: a model was rolled out at scale with no independent validation, so its real performance was far worse than advertised, and nobody could see the gap. For a life-or-death task, the metric that matters most is **recall**, because a missed case can kill.

### AWS Services / Practices That Could Mitigate It

- **SageMaker Model Monitor** — continuously track live performance and catch the drop-off between claimed and real accuracy.
- **SageMaker Clarify** — explain why an alert fired, opening up the black box.
- **SageMaker Model Cards** — document intended use, validated performance, and limitations before deployment.
- **Amazon A2I** — send uncertain predictions to a human for review instead of blindly alerting.
- **AWS Audit Manager** — enforce independent validation before go-live, not just trust in vendor numbers.

### Lesson

The ethical failure was deploying a high-stakes AI model without the monitoring, transparency, and independent validation that responsible AI demands.

---

## Reference

Wong A, Otles E, Donnelly JP, et al. *External Validation of a Widely Implemented Proprietary Sepsis Prediction Model in Hospitalized Patients.* JAMA Internal Medicine, 2021.

Link: https://pubmed.ncbi.nlm.nih.gov/34152373/

> Note: The hospitals studied used Epic's system, not AWS. The AWS services listed above are an applied analysis of how this class of failure could be prevented if the model were built and governed responsibly on AWS. The case itself is real and peer-reviewed; the AWS mapping is the applied reasoning.