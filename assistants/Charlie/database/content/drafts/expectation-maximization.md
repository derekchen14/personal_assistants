---
title: "Expectation Maximization"
---

## _hidden_section_title
Real-world data is rarely clean. Records go missing, labels are absent, and meaningful patterns hide beneath noise.

Most algorithms treat that messiness as something to eliminate. They scrub, impute, or discard incomplete records before training even begins.

Expectation Maximization (EM) takes the opposite approach. It folds uncertainty directly into the learning process, treating incomplete records as a working ingredient rather than an obstacle. That shift lets EM thrive where other algorithms stall, powering anomaly detection, customer segmentation, speech recognition, and unsupervised clustering — none of which require clean input data.

At its core, EM alternates between two steps in a repeating feedback loop.

The **E-step** (Expectation) evaluates each data point against the current model parameters. It assigns each point a probability weight for every cluster or hidden state.

The **M-step** (Maximization) uses those weighted assignments to update the parameters, finding the values that best explain what the E-step observed.

The cycle continues until the parameters stabilize and the likelihood stops climbing.

The sections that follow unpack the mathematics behind EM and walk through a worked example. By the end, you will understand not just how EM works, but why it works.

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