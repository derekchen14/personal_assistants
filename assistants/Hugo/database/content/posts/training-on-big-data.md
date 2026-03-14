---
layout: post
title: Deep Learning using GPUs in the Cloud
date: '2016-01-11 04:16:29'
tags:
- gpu
- aws
---

Recent advances in Deep Learning have come about for a couple of key reasons, not the least of which is the enormous growth of available data.  But if overwhelming amounts of data are required to reach peak performance, how does one actually go about managing the unmanageable?  In other words, how does one get past the hype of Big Data in machine learning and into the practical implementation of leveraging Big Data for meaningful results?

**What Are My Options?**

It turns out that quite often distributed cloud computing with Apache Hadoop, Spark, or Storm is neither the most efficient nor the most effective method of training machine learning algorithms when dealing with massive datasets.  [Other articles](fastml.com/the-emperors-new-clothes-distributed-machine-learning/) will dig into the details, but the gist is the overhead necessary to manage a complicated MapReduce architecture usually outweighs the benefits gained by being able to scale indefinitely with commodity hardware.  Simply put, if you're still debating whether you qualify as a Big Data company, then you don't have enough data yet, and using a single high-powered machine is your best bet.

After coming to the conclusion that all you need is a couple of multi-core GPUs, there are two routes: buy or rent.  The former option means [building a custom computer](https://www.reddit.com/r/MachineLearning/comments/3wk6wl/tips_on_buyingbuilding_a_computer_with_a_gpu_for/) with powerful specs, and is largely a decision of how much you are willing to spend on a graphics card.  If you truly want a personalized machine, then this is the way to go.  However, for most practical purposes, renting a GPU through AWS is preferable because not only will it cost less in the short term, but you can also scale up in power and in the number of servers if the need arises.  Therefore, the remainder of this article will deal with how to setup and configure a GPU instance on Amazon Web Services.

**Setting Up GPUs on AWS**

If you have worked with EC2 before on AWS, then running deep learning models on GPUs will be a breeze because the process is almost identical to running programs on CPUs.  And if you have not done that before, don't worry, because Amazon has made the new user experience relatively painless as well.  Once you've created an account, the key steps are:

  * A. Launch an EC2 Instance ![Management Console](/content/images/2016/01/EC2_Management_Console.png)
  * B. Walk through the steps outlined in the top row:
     1. *Select an AMI* - Choose a community AMI with what you want pre-installed.  For the time being (Jan 2016), I am hosting a preconfigured set-up that comes with most of the libraries you hopefully need for Deep Learning. In particular, `Keras for Deep Learning (ami-5ea7d23e)` comes with Theano, TensorFlow, Keras and CUDA7 pre-installed.  If you truly want to go through the pain of setting everything up yourself, choose `64-bit Ubuntu 14.04 LTS (ami-3d50120d)` from the Quick Start list and follow the directions [found here](http://markus.com/install-theano-on-aws/). ![AWS AMI Setup](/content/images/2016/01/EC2_Step1.png)
     2. *Choose an instance type* - Select "GPU Instances" from the "All Instance Types" dropdown, and pick `g2.2xlarge` from the list.  That's it!  You have just gone from CPU-computing to GPU-computing! ![AWS_Instance](/content/images/2016/01/EC2_Step2.png)
     3. *Configure instance* - Choose spot instances if desired, will save a couple of dollars for every full day you plan on keeping your instance running. ![AWS Spot](/content/images/2016/01/EC2_Step3.png)
     4. *Add storage* - add more EBS (Elastic Block Store) storage if so desired.  If your data set is larger than 32 GB, then you might need to explore this option, otherwise feel free to leave as is.
     5. *Tag instance* - add some tags to help identify this instance.  Unless you already have many instance running, in most cases, you can leave this section blank.
     6. *Configure security group* - ==Important!== This section outlines who will be able to access your instance.  By default, allowing SSH with a TCP protocol coming from your own IP will allow you to connect into the terminal of your instance and perform secure copies.  If you're working from multiple locations, then add some more IPs.  If you're using other tools, then add more ports. For example, using a Rails server usually uses port 3000 and iPython Notebooks default to using port 8888. ![Security Group](/content/images/2016/01/EC2_Step6.png)
     7. *Review* - Check all your details and then click [Launch]
  * C. Save your PEM
    1. The next dialog box will prompt you to create your security key
    2. Once that is done, download your PEM in a secure and accessible location since you will need it each time to access your instance
    3. Modify the access to the PEM to make it private with chmod 0400.
  * D. Access your machine
    1. Use  `ssh -i <pem_file_name>.pem <username>@<your instance full dns address>` to get in, with username usually being Ubuntu, ec2-user, or root.  The pem_ file_name is the name of the file you created in Step C2
    3. A completed example might look like `ssh -i EC2_GPU_22x.pem ubuntu@ec2-52-29-214-135.us-west-1.compute.amazonaws.com`
    2. Use `scp -r -i <pem_file_name>.pem setup/ <username>@<full dns address>:~` to copy a folder into your instance.  In this case "setup" is the name of your folder. This command is performed from your local machine.  A similar command can be performed on your remote to [download files](http://stackoverflow.com/questions/11304895/how-to-scp-a-folder-from-remote-to-local) into your local computer.

**Common Pitfalls**

If you're following this tutorial or others you've found online, you might still encounter some issues.  This is where I hope to add to the discussion to prevent hours of headache and searching through StackOverflow.  Some common issues include:

  1. You forgot to add a credit card to AWS or your credit card is expired.  Also, if your bank has recently issued you a new card because they were breached again, you will also need to update your credentials.
  2. You didn't remember the password for your remote so you weren't able to use `sudo`. Now I know you didn't even try to enter the command, because on a remote machine, you don't need the password :)
  3. You skipped Step C3 which limits the access to your PEM file. This will result in an error complaining about "Unprotected Private Key File: Permissions 0777 for '.ssh/my_ private_key.pem' are too open.  It is required that your private key files are NOT accessible by others. This private key will be ignored." To fix the error, execute the following command, substituting the path for your private key file: `$ chmod 0400 .ssh/my_private_key.pem`.
  4. You used the wrong host key, resulting in "Error: Host key not found, Permission denied (publickey), or Authentication failed, permission denied".  To fix this, replace the <username> portion with `Ubuntu`.  If that doesn't work, try `ec2-user`.  If that doesn't work, try `root`.  If that doesn't work, start googling.
  5. You moved out of your home and into a coffeeshop, but then you forgot to add the IP of the coffeeshop to your list of allowed IPs in "Configure Security Groups" in Step B6. To fix this, find "Network & Security" on the left panel.  Then select Security Groups > check the box > Actions > Edit Inbound Rules > add your IP > Save
  6. You didn't upgrade your packages and now the system is complaining.  Even when you choose an existing public AMI from the community, their setup might be out of date.  It is up to you to run system updates with `sudo apt-get -y dist-upgrade` and library updates with `sudo pip install --upgrade <package name>`
  7. Anything else you see on this list: http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/TroubleshootingInstancesConnecting.html

**Saving your Image**

If you added more packages or did some more set-up, you might want to save your own AMI for future use.  This will cost you a couple dollars a year, but it's a great idea if you plan to use the same configuration for multiple projects or if you're using the company budget to fund the project.   To do this, you simple go to Images on the left-hand panel and then select AMIs > check the box > Actions > Save Image.  If you are doing other configuration work, keep in mind that you likely have an EBS-backed image and not an Instance Store-back image. ![AWS Image](/content/images/2016/01/EC2_Image.png)
And with that you're done! You now have a custom machine built for specifically for your machine learning purposes that you can use at any time.  Leave any questions or comments in the section below!
