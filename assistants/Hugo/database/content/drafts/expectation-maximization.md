---
layout: post
title: Expectation Maximization
---

Expectation maximization is often used to fill in blanks when there is missing data by imputing those values by considering what makes the most sense.  Use cases include anomaly detection, market segmentation, speech recognition and basic clustering.  The algorithm operates by iteratively alternating between two steps until convergence: the E-step for expectation and the M-step for maximization.

|         | E-step           | M-step  |
| ------------- |:-------------:| -----:|
| K-means      | right-aligned | $1600 |
| Gaussian Mixture Model      | centered      |   $12 |
| zebra stripes | are neat      |    $1 |


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

  The E-step typically consists of assigning weights to data based on parameters (calculate p(y|x, )).  