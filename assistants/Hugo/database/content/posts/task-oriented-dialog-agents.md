---
layout: post
title: Task-Oriented Dialog Agents
date: '2017-12-03 20:42:05'
---

![cs221_poster](/content/images/2017/12/cs221_poster_resized.jpeg)

[Link to 1st Paper](https://www.dropbox.com/s/o573a81j4dms6jv/goal-oriented-dialog-cs229.pdf?dl=0)

[Link to 2nd Paper](https://www.dropbox.com/s/gd5pb3166lst6sw/goal-oriented-dialog-cs221.pdf?dl=0)

**Description**

The past five years has seen an explosion in dialog agents, including voice-activated bots such as Siri, chatbots on Slack, or email-based bots for scheduling meetings.  As the prevalence of such personal assistants continues to grow, so too does the desire for increased capabilities. However, many of these so-called intelligent agents fall short of expectations, often failing to return any useful information to the user.  If the abilities of dialog agents were incrementally improved though, it would not be hard to imagine reaching a tipping point where a number of real-world tasks are replaced or automated by such systems.  Consequently, the main goal of this project is to apply techniques and ideas from class to build an effective task-oriented dialog system.  As a stretch goal, we hope to expand on the state-of-the-art accuracy currently occupied by various sequence-to-sequence learning algorithms.

**Scope and Challenges**

Building a task-oriented dialog agent can be seen as a language modeling problem where the input is sentences from a user or customer, and the output is a generated sentence along with any pertinent information required to help the user complete their task.  More specifically, the user might desire to find a place to eat, and the job of the agent is to complete a coherent conversation while also finding a restaurant meeting the user’s criteria. 
The scope of our project is purely chat based, which is to say we are not planning to build a SDS (spoken dialog system) like Alexa, and so we will not be transcribing speech or generating audio.  Additionally, our bot is focused only on task-oriented dialog, and is not geared towards open-domain chit-chat. Even with those limitations, numerous challenges remain.  
Concretely, a task-oriented bot will need to process user input, model user intent, query a KB for a desired object, and generate a meaningful, coherent response.  Furthermore, the agent should manage to do this across multiple turns, for multiple objects, and possibly while the user changes their mind halfway through the dialog.  To address these challenges, we will use RNNs and beam search to generate responses.  We also have to model beliefs, which is like the “state” of the user.

**Evaluation**

For this project, we will be using data from two separate sources.  First, we will be working with Task 6 from the BaBI Dialog Dataset, put together by Facebook and described in detail within Learning End-to-End Goal-Oriented Dialog.  This data is based off the DSTC2 (Dialog State Tracking Challenge) organized by the University of Cambridge.  Second, we will be working with a multi-domain car-related dataset from Stanford NLP group found in Key-Value Retrieval Networks for Task-Oriented Dialogue, created in collaboration with Ford Motor Company.  The bAbI dataset employs per-turn accuracy and per-dialog accuracy to gauge progress, while the car dataset relies on Entity F1-score.  Additionally, we will also look to word overlap metrics such as BLEU to measure language modeling success.  Finally, we plan to randomly sample from various dialogs to perform human evaluation on whether or not a task was successfully completed.

For the baseline and oracle, we randomly selected data from the datasets and set up a program to display dialogs.  Then for 50 examples per task, the agent is graded on the per-turn and per-dialog accuracy.  We define per-turn accuracy as the number of correct api calls and responses given by the agent, and the per-dialog accuracy as getting all turns correct in an example.
To implement a baseline, we use TF-IDF matching to select a response for a query from a list of 2000+ candidate responses.   More specifically, we have set up a pipeline with SK-Learn to vectorize the query, and then select the response with the closest cosine distance.   
