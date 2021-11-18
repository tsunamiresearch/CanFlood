.. _introduction:

============================
1. Introduction
============================

CanFlood is an object-based, transparent, open-source flood risk calculation toolbox built for Canada. CanFlood facilitates flood risk calculations with three ‘toolsets’:

  1) Building a model  |buildimage|                      

  2) Running a model   |runimage|                       
  
  3) Visualizing and analyzing results   |visualimage|

Each of these has a suite of tools to assist the flood risk modeller in a wide range of tasks common in developing flood risk assessments in Canada.

CanFlood flood risk models are object-based, where consequences from flood exposure are calculated for each asset (e.g., a house) using a one-dimensional user-supplied vulnerability function (i.e., depth-damage function) before summing the consequences on each asset and integrating a range of events to obtain the total flood risk in an area. To support the diversity of flood risk assessment needs and data availability across Canada, CanFlood supports three modelling frameworks of increasing complexity, data requirements, and effort (Section1.1_). Each of these frameworks was designed to be flexible and agnostic, allowing modellers to implement a single software tool and data structure while maintaining flood risk models that reflect the heterogeneity of Canadian assets and values. Recognizing the significance of flood protection infrastructure on flood risk in many Canadian communities, CanFlood models can incorporate failure potential into risk calculations. To make use of Canada’s growing collection of hazard modelling datasets, CanFlood helps users connect with and manipulate such data into flood risk models.

The CanFlood plugin is NOT a flood risk model, instead it is a modelling platform with a suite of tools to aid users in building, executing, and analyzing their own models. CanFlood requires users to pre-collect and assemble the datasets that describe flood risk in their study area (see Section0_). Once analysis in CanFlood is complete, users must apply their own judgement and experience to attach the necessary context and advice to any reporting before communicating results to decision makers. CanFlood results should not be used to *make* decisions, instead they should be used to *inform* decisions along with all the other dimensions and criteria relevant to the community at risk.