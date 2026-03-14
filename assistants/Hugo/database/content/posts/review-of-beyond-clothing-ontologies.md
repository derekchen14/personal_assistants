---
layout: post
title: Clothing Ontologies for Fashion Recommendations
date: '2016-08-21 03:50:58'
---

Within the Beyond Clothing Ontologies: Modeling Fashion with Subjective Influence Networks, the authors Kurt Bollacker, Natalia Díaz-Rodríguez, Xian Li (from Stitch Fix) have presented a supplementary fashion ontology for modeling out the relationships of clothing that go beyond other existing ontologies by taking into account deeper subjective measures, namely influence networks, rather than just objective measures of clothing, such as length of sleeve or material.  While related schemas on have been proposed in the past, they fall short from being useful because they fail to incorporate many subjective aspects of fashion, such as where a style originated from or how a particular design was influenced by past trends.

The model itself first proposes that all garments (g) can be processed through any number of subjective judge functions (s) that then label each of the garments as belonging to a certain style.  Each style is then modeled as a directed acyclic-graph that maps out where the style originated and the ideas that influenced the style.  In crafting this graph, each element of influence is measured using a quad of variables:

  - **t**: amount of elapsed time between the influencing and influenced style
  - **i**:  intensity or strength of influence
  - **m**: mechanism of influence
  - **a**: agent of influence.

While *t* and *i* can both be represented as positive reals, *m* is a class that exists in a vast space of possible Mechanisms.  Numerous possible applications are also presented for the ontology, such as search result rankings, fashion data retrieval, and recommending items to shoppers.

The overall idea seems to point in the right direction, but not give a clear sense on how the various components of the style function might be implemented, or where such training data might come from.  When performing this work in the real world, rather than in academia, many trade-offs will probably be made along the way, so seeing what a concrete implementation looks like would have been nice.  To be fair, the authors readily admit that such an ontology is incomplete until the various variables mentioned above have set defaults along with methods to explicitly calculate (or at least approximate) the outcome of style function.

Separately, I wonder how useful it is to have an explicitly mapped ontology, whether subjective or objective in nature.  Isn't a large advantage of modern deep learning that ability to skip many traditional feature engineering stages and let the network figure out how all the data points are connected?  To be clear, if someone were willing label the history of influence for each and every piece of clothing, then such a data point should not be ignored, but to the extent that such data exists, wouldn't that simply make the neural net that much more powerful as well?  

In the end, the most promising idea to me is actually the sense that if such an ontology could be properly built, perhaps using some modified word2vec as proposed by the authors, then such a system could *also* be implemented for a wide variety of other use cases - recommending music, restaurants, electronic gadgets, places to work, classes to study.

Overall, I still appreciate all research papers that explore the space around using deep learning as a foundation for practical use cases. In particular, given deep learning is a cutting edge technology then recommendation systems can be viewed as a practical application of that technology.  However, the industry still has not bridged the gap between the two processes, so anything that helps us get a better grasp of how that might be possible is critical to bringing a meaningful AI revolution.