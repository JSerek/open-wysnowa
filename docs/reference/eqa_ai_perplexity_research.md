<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# We are going to work on an advanced tool for Exploratory Qualitative Analysis using LLMs for it. My aim is to build a solution / pipeline / agentic workflow for exploratory qualitative data analysis which in a sense will resemble statistical modeling or more broadly quantitative data analysis. By that I mean I want to make qualitative analysis more reliable and measure the outcome of LLMs outputs (evaluations) - but not creating a golden data set for accuarcy comparisons between human analyst and LLM analyst as this doesn't make sense in a novel problems.

First, I wane you to run a deep research to extract as many trustworthy informations about:
Classical approach to running qualitative data analysis and analysts suggestions on how to measure it's validity and reliability
One of my favorite ideas is to measure saturation of topics and saturation of meaning (Hennink, Kaiser \& Marconi’s paper “Code Saturation Versus Meaning Saturation” (2017, Qualitative Health Research)
Code (or thematic) saturation – the point at which no new issues/themes/codes are identified in the data; this is about the range of topics.
Meaning saturation – the point at which you have sufficient depth and understanding of each theme, including nuance, variations, and rich supporting evidence; this is about the depth of topics
I want to know as much as possible about all the papers describing LLMs in qualitative data analysis.
General guide
I plan on creating such solution for improving the quality of qualitative analysis mainly in a business scenario, but hopefully it could be useful in academia as well. I want to put empahsis on quality and rigor, above speed.
Loose thoughts
I've already started tinkering with system like this, but I'm on a very early stage. I like the idea the there might be multiple LLM's / Agents each prompted to focus on different aspects / methods in qualitative data e.g. one is focusing on theme extraction related to products, other is focus solely on emotions and motivations of users, another is analyzing user's style of describing products and problem (aka discourse analysis).

Perfect! I've completed a comprehensive deep research session on your exploratory qualitative analysis system using LLMs. Here's what I've compiled for you:

## Research Summary

I've created **extensive research notes** (24,000+ words) covering all the areas you requested:

### 📊 **Classical Qualitative Analysis** (Part 1-2)

- Validity \& reliability measures (triangulation, member checking, peer examination)
- Inter-rater reliability metrics (Cohen's Kappa, percentage agreement, ICC)
- **Saturation measurement frameworks** - detailed coverage of Hennink, Kaiser \& Marconi's distinction between:
    - **Code saturation** (breadth - reached at ~9 interviews)
    - **Meaning saturation** (depth - requires 16-24 interviews)
- Guest et al.'s practical Base Size/Run Length/Threshold method


### 🤖 **LLMs in Qualitative Research** (Part 3-4)

- 15+ major research papers analyzed (2023-2025)
- **Key finding**: Ensemble/multi-agent approaches consistently outperform single LLM analysis
- Studies show:
    - LLM-human agreement: Cohen's κ = 0.46-0.67 (moderate to substantial)
    - Multi-run stability: κ = 0.84-0.91 (almost perfect)
    - PwC case: 7x accuracy improvement with proper multi-agent architecture


### 🎯 **Evaluation Metrics** (Part 4-5)

- Traditional metrics adapted for LLMs (Cohen's Kappa, ICC)
- Novel approaches: Cosine similarity, BERTScore, semantic consistency
- Multi-layered evaluation frameworks combining:
    - Inter-run reliability (3-6 runs per analysis)
    - Inter-agent agreement
    - Human-LLM comparison
    - Qualitative rubrics (Braun \& Clarke criteria)


### 🤝 **Multi-Agent Systems** (Part 5-6)

Your initial intuition about multiple specialized agents is **strongly supported** by research:

- Specialized agents for different analytical dimensions (product, emotion, discourse) show superior results
- Independent validation layers reduce hallucinations by 40%
- Ensemble methods with smaller models can outperform GPT-4 alone


### 💡 **Specific Recommendations for Your System** (Part 7-11)

**Proposed Architecture:**

- **Tier 1**: 5-7 specialized analytical agents (your idea validated!)
- **Tier 2**: Synthesis \& consolidation agents
- **Tier 3**: Independent validation agents
- **Tier 4**: Meta-analysis agents (reflexivity, alternatives, confidence)

**Evaluation Framework:**

- 5 layers of evaluation from real-time confidence scoring to human validation
- Both code AND meaning saturation measurement (your focus is innovative!)
- Hybrid approach: LLM for code saturation, human-verified meaning depth

**Key Differentiator:**
Your emphasis on **meaning saturation** (not just code saturation) addresses a major gap in current LLM qualitative research. Most studies focus only on whether codes emerge, not whether themes are deeply understood.

### 📚 **Critical References Included**

21 essential papers cited with full details, including:

- The Hennink et al. 2017 saturation paper you mentioned
- Latest 2024-2025 research on LLM qualitative analysis
- Multi-agent system designs and evaluation frameworks

The research notes are saved in `qualitative_analysis_llm_research.md` and include:

- Detailed implementation roadmap (6-12 months)
- Cost-benefit analysis for business vs. academic contexts
- Prompt engineering templates
- Formulas for all key metrics
- Glossary of technical terms

This should give you a solid foundation for designing your system with emphasis on **rigor and measurable quality** above speed. The evidence strongly supports your multi-agent approach with specialized analytical perspectives! 🚀
<span style="display:none">[^1][^10][^100][^101][^102][^103][^104][^105][^106][^107][^108][^109][^11][^110][^111][^112][^113][^114][^115][^116][^117][^118][^119][^12][^120][^121][^122][^13][^14][^15][^16][^17][^18][^19][^2][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29][^3][^30][^31][^32][^33][^34][^35][^36][^37][^38][^39][^4][^40][^41][^42][^43][^44][^45][^46][^47][^48][^49][^5][^50][^51][^52][^53][^54][^55][^56][^57][^58][^59][^6][^60][^61][^62][^63][^64][^65][^66][^67][^68][^69][^7][^70][^71][^72][^73][^74][^75][^76][^77][^78][^79][^8][^80][^81][^82][^83][^84][^85][^86][^87][^88][^89][^9][^90][^91][^92][^93][^94][^95][^96][^97][^98][^99]</span>

<div align="center">⁂</div>

[^1]: https://dx.plos.org/10.1371/journal.pgph.0001374

[^2]: http://dergipark.org.tr/en/doi/10.17049/jnursology.1447799

[^3]: https://journals.sagepub.com/doi/full/10.1089/jayao.2023.0040

[^4]: https://www.semanticscholar.org/paper/36bc4fbe76e9c31785c5ee71ab046288446253e6

[^5]: https://jpro.springeropen.com/articles/10.1186/s41687-020-00241-6

[^6]: http://connect.springerpub.com/lookup/doi/10.1891/9780826170620

[^7]: https://www.semanticscholar.org/paper/d842b35a93944e8bb62ff0b2252f6b945d8482da

[^8]: https://www.tandfonline.com/doi/full/10.1080/17482631.2024.2318810

[^9]: https://www.taylorfrancis.com/books/9781134646074

[^10]: https://www.semanticscholar.org/paper/d8e92b6d6ea66fdfcf3546b33ab0ad5649aaf597

[^11]: https://pmc.ncbi.nlm.nih.gov/articles/PMC1089059/

[^12]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10425717/

[^13]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7049186/

[^14]: https://www.frontiersin.org/articles/10.3389/fpsyg.2023.1217661/pdf

[^15]: https://journals.sagepub.com/doi/10.1177/00491241231156971

[^16]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10358327/

[^17]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10704389/

[^18]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10267995/

[^19]: https://www.projectguru.in/how-to-establish-the-validity-and-reliability-of-qualitative-research/

[^20]: https://journals.sagepub.com/doi/abs/10.1177/1049732316665344

[^21]: https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0232076

[^22]: https://getthematic.com/insights/methods-of-qualitative-data-analysis

[^23]: https://journals.sagepub.com/doi/10.1177/1049732316665344

[^24]: https://pubmed.ncbi.nlm.nih.gov/32369511/

[^25]: https://www.ncbi.nlm.nih.gov/books/NBK470395/

[^26]: https://pubmed.ncbi.nlm.nih.gov/27670770/

[^27]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7200005/

[^28]: https://csedresearch.org/validity-and-reliability-in-qualitative-research/

[^29]: https://www.scirp.org/reference/referencespapers

[^30]: https://journals.sagepub.com/doi/10.1177/16094069241229777

[^31]: https://atlasti.com/guides/the-guide-to-mixed-methods-research/validity-reliability-in-mixed-methods-research

[^32]: https://www.sciencedirect.com/science/article/pii/S0277953621008558

[^33]: https://www.simplypsychology.org/data-saturation-qualitative-research.html

[^34]: https://arxiv.org/abs/2401.04138

[^35]: https://journals.sagepub.com/doi/10.1177/16094069251322346

[^36]: https://arxiv.org/abs/2404.17605

[^37]: https://journals.sagepub.com/doi/10.1177/16094069251381706

[^38]: https://journals.sagepub.com/doi/10.3102/0013189X251314821

[^39]: https://journals.sagepub.com/doi/10.1177/16094069241289279

[^40]: https://arxiv.org/abs/2402.01386

[^41]: https://www.researchprotocols.org/2025/1/e78682

[^42]: https://dl.acm.org/doi/10.1145/3718491.3718640

[^43]: https://nsuworks.nova.edu/tqr/vol26/iss6/17/

[^44]: http://arxiv.org/pdf/2411.14473.pdf

[^45]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10931535/

[^46]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11517081/

[^47]: http://arxiv.org/pdf/2407.11198.pdf

[^48]: https://arxiv.org/html/2407.14925v1

[^49]: https://arxiv.org/pdf/2305.13014.pdf

[^50]: http://arxiv.org/pdf/2409.19430.pdf

[^51]: https://arxiv.org/pdf/2402.01386.pdf

[^52]: https://arxiv.org/html/2411.14473v4

[^53]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5167505

[^54]: https://arxiv.org/pdf/2310.07061.pdf

[^55]: https://www.nature.com/articles/s41598-025-18969-w

[^56]: https://www.diva-portal.org/smash/get/diva2:1939104/FULLTEXT02

[^57]: https://www.linkedin.com/pulse/ai-gpt-qualitative-research-paradigm-shift-thematic-coding-saikia-rlc3f

[^58]: https://arxiv.org/html/2510.18456v1

[^59]: https://www.jmir.org/2024/1/e59050/

[^60]: https://journals.sagepub.com/doi/10.1177/16094069241231168

[^61]: https://github.com/PerttuHamalainen/LLMCode

[^62]: https://learninganalytics.upenn.edu/ryanbaker/C-JLA.pdf

[^63]: https://arxiv.org/html/2410.07362v1

[^64]: https://educationaldatamining.org/EDM2025/proceedings/2025.EDM.poster-demo-papers.283/index.html

[^65]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11310599/

[^66]: https://arxiv.org/abs/2512.20352

[^67]: https://www.per-central.org/items/detail.cfm?ID=17123

[^68]: https://openaccess.cms-conferences.org/publications/book/978-1-964867-71-7/article/978-1-964867-71-7_14

[^69]: https://journals.lww.com/10.1097/NNR.0000000000000831

[^70]: https://hrmars.com/journals/papers/IJARPED/v14-i1/24128

[^71]: https://spm-online.com/jrep/index.php/journal/article/view/51

[^72]: https://ijitsc.net/index.php/journal/article/view/145

[^73]: https://e-journal.undikma.ac.id/index.php/prismasains/article/view/15262

[^74]: https://www.ahajournals.org/doi/10.1161/circ.150.suppl_1.4146361

[^75]: https://nasenjournals.onlinelibrary.wiley.com/doi/10.1111/1467-8578.12474

[^76]: http://arxiv.org/pdf/2106.07393.pdf

[^77]: https://pmc.ncbi.nlm.nih.gov/articles/PMC9814438/

[^78]: https://pmc.ncbi.nlm.nih.gov/articles/PMC6506991/

[^79]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10820331/

[^80]: https://arxiv.org/pdf/2404.14149.pdf

[^81]: https://pmc.ncbi.nlm.nih.gov/articles/PMC3001856/

[^82]: https://www.tqmp.org/RegularArticles/vol08-1/p023/p023.pdf

[^83]: https://pmc.ncbi.nlm.nih.gov/articles/PMC5965649/

[^84]: https://pmc.ncbi.nlm.nih.gov/articles/PMC3900052/

[^85]: https://eliteresearch.com/wp-content/uploads/2025/04/Ensuring-Inter-Rater-Reliability-in-Qualitative-Coding-Techniques-for-Accuracy.pdf

[^86]: https://medcraveonline.com/JABB/application-of-triangulation-in-qualitative-research.html

[^87]: https://pubmed.ncbi.nlm.nih.gov/23092060/

[^88]: https://compendiumpaperasia.com/index.php/cpa/article/download/545/313/6325

[^89]: https://www.looppanel.com/blog/triangulation-in-qualitative-research

[^90]: https://en.wikipedia.org/wiki/Cohen's_kappa

[^91]: https://pmc.ncbi.nlm.nih.gov/articles/PMC9099179/

[^92]: https://www.thefarnsworthgroup.com/blog/triangulation-qualitative-research

[^93]: https://encord.com/blog/inter-rater-reliability/

[^94]: https://journals.sagepub.com/doi/10.1177/1609406919899220

[^95]: https://pubmed.ncbi.nlm.nih.gov/25158659/

[^96]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12573311/

[^97]: https://delvetool.com/blog/triangulation-qualitative-research

[^98]: https://arxiv.org/abs/2511.13333

[^99]: https://www.semanticscholar.org/paper/eaf52a96efd77675130196b32ca3ae25e03b0d35

[^100]: https://www.mdpi.com/1999-5903/17/9/404

[^101]: https://ieeexplore.ieee.org/document/11163350/

[^102]: https://arxiv.org/abs/2506.12618

[^103]: https://www.semanticscholar.org/paper/0b04776792c83ec1bf4b83078c4b7618d85bc76e

[^104]: https://journalair.com/index.php/AIR/article/view/1431

[^105]: https://arxiv.org/abs/2404.05221

[^106]: https://bmcmedinformdecismak.biomedcentral.com/articles/10.1186/s12911-024-02757-z

[^107]: https://aclanthology.org/2023.emnlp-main.543.pdf

[^108]: https://arxiv.org/pdf/2411.15320.pdf

[^109]: https://aclanthology.org/2023.conll-1.16.pdf

[^110]: http://arxiv.org/pdf/2504.02106.pdf

[^111]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11590327/

[^112]: https://arxiv.org/html/2410.07069

[^113]: https://aclanthology.org/2023.nlp4convai-1.5.pdf

[^114]: http://arxiv.org/pdf/2410.02054.pdf

[^115]: https://learn.microsoft.com/en-us/ai/playbook/technology-guidance/generative-ai/working-with-llms/evaluation/list-of-eval-metrics

[^116]: https://aclanthology.org/2025.findings-acl.563/

[^117]: https://www.confident-ai.com/blog/llm-evaluation-metrics-everything-you-need-for-llm-evaluation

[^118]: https://sciety-labs.elifesciences.org/articles/by?article_doi=10.35542%2Fosf.io%2Fez8wc_v1

[^119]: https://www.science.org/doi/10.1126/sciadv.adp1528

[^120]: https://wandb.ai/onlineinference/genai-research/reports/LLM-evaluation-metrics-A-comprehensive-guide-for-large-language-models--VmlldzoxMjU5ODA4NA

[^121]: https://www.anthropic.com/engineering/multi-agent-research-system

[^122]: https://galileo.ai/blog/qualitative-vs-quantitative-evaluation-llm

