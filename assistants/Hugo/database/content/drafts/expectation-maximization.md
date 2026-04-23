---
title: "Expectation Maximization"
---

## _hidden_section_title
Real-world data is rarely clean. Records go missing, labels are absent, and patterns hide beneath the noise. Most machine learning algorithms treat incomplete data as a problem to fix — scrubbing, imputing, or discarding it before training begins. Expectation Maximization (EM) takes the opposite approach. It estimates missing information directly from the data, turning incomplete records into a working ingredient rather than an obstacle.

EM thrives where other algorithms stall. It powers anomaly detection, customer segmentation, speech recognition, and unsupervised clustering. At its core, EM alternates between two steps. The **E-step** (Expectation) uses the current model parameters to assign each data point a probability weight. That weight reflects how likely the point belongs to each cluster or hidden state. The **M-step** (Maximization) then updates the parameters to best explain those weighted assignments. Each iteration improves the model's fit. The cycle repeats until the parameters stabilize and the likelihood stops climbing.

The sections that follow unpack the mathematics behind EM and walk through a worked example. We'll also explore why this iterative design handles incomplete data so well. By the end, you'll understand not just how EM works, but why it works.
## Results

|         | E-step           | M-step  |
| ------------- |:-------------:| -----:|
| K-means      | right-aligned | $1600 |
| Gaussian Mixture Model      | centered      |   $12 |
| zebra stripes | are neat      |    $1 |


## Table View

<table>
    <tr>
        <td>Row 1, cell 1</td>
        <td>Row 1, cell 2</td>
        <td>Row 1, cell 3</td>
    </tr>
    <tr>
        <td>Row 2, cell 1</td>
        <td>Row 2, cell 2</td>
        <td>Row 2, cell 3</td>
    </tr>
    <tr>
        <td>Row 3, cell 1</td>
        <td>Row 3, cell 2</td>
        <td>Row 3, cell 3</td>
    </tr>
    <tr>
        <td>Row 4, cell 1</td>
        <td>Row 4, cell 2</td>
        <td>Row 4, cell 3</td>
    </tr>
</table>

The E-step assigns weights to each data point using the current model parameters. The weight is the probability p(y|x).