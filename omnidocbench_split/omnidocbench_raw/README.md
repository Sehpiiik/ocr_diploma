# OmniDocBench

[English](./README.md) | [简体中文](./README_ZH.md)

**OmniDocBench** is an evaluation dataset for diverse document parsing in real-world scenarios, with the following characteristics:
- **Diverse Document Types**: The evaluation set contains **1651** PDF pages, covering **10** document types, **5** layout types and **5** language types. Coverage includes academic literature, research and financial reports, newspapers, textbooks, exam papers, magazines, handwritten notes, historical documents, and more.
- **Rich Annotations**: Contains localization for **28** block-level categories (text paragraphs, titles, tables, formulas, headers/footers, etc.) and **4** span-level categories (text lines, inline formulas, superscripts/subscripts, etc.), plus recognition results for each region (text, LaTeX for formulas, LaTeX and HTML for tables). OmniDocBench also provides reading-order annotations for layout elements. Page- and block-level attribute labels include **5** page attribute categories, **3** text-related attributes and **6** table-related attributes.
- **High Annotation Quality**: Through manual screening, intelligent annotation, manual annotation, full expert quality inspection and large model quality inspection, the data quality is relatively high.
- **Evaluation Code Suite**: Designed with end-to-end evaluation and single module evaluation code to ensure fairness and accuracy of evaluation. The evaluation code suite can be found at [OmniDocBench](https://github.com/opendatalab/OmniDocBench).

## Updates

- [2026/04/09] (1) Added a **296-page** hard subset for difficult formulas, tables, and layouts; (2) Corrected part of the table, formula, and OCR annotations from v1.5. The full **1651-page** release is in `OmniDocBench.json`.
- [2025/09/25] (1) Newspaper and note images were upgraded to **200 DPI**; fixed some OCR and table GT issues from v1.0. (2) To balance Chinese and English pages and increase pages with formulas, **374** pages were added (25 Chinese, 349 English), including books, PPT-to-PDF, colorful textbooks, exam papers, magazines, and newspapers; display (`equation_isolated`) formulas increased from **353** to **1050**; formula language attributes were added (**68** Chinese display formulas, **982** English display formulas).
- [2024/12/25] Added PDF format of the evaluation set for models that require PDFs as input for evaluation. Added original PDF slices with metadata.
- [2024/12/10] Fixed height and width fields for some samples. This fix only affects page-level height and width fields and does not impact the correctness of other annotations
- [2024/12/04] Released OmniDocBench evaluation dataset

## Dataset Introduction

The evaluation set contains **1651** PDF pages, covering **10** document types, **5** layout types and **5** language types. OmniDocBench has rich annotations, including **28** block-level categories (text paragraphs, titles, tables, formulas, headers/footers, etc.) and **4** span-level categories (text lines, inline formulas, superscripts/subscripts, etc.). All text-related annotation boxes contain text recognition annotations, formulas contain LaTeX annotations, and tables contain both LaTeX and HTML annotations. OmniDocBench also provides reading order annotations for document components. Additionally, it includes various attribute labels at page and block levels, with 5 page attribute categories, 3 text attribute labels and 6 table attribute labels.

![](data_diversity.png)

## Usage

You can use our [evaluation method](https://github.com/opendatalab/OmniDocBench) to conduct evaluations across several dimensions:

- End-to-end evaluation: Includes both end2end and md2md evaluation methods
- Layout detection
- Table recognition
- Formula recognition
- Text OCR

The evaluation dataset files include:

- [OmniDocBench.json](OmniDocBench.json) is the full annotation file for the evaluation dataset (**1651** pages), stored in JSON format. It supports the end2end evaluation method. The structure and fields are explained below.
- [images](./images/) are the corresponding evaluation dataset images, for models that require images as input.
- [image_to_pdf.py](https://github.com/opendatalab/OmniDocBench/blob/main/tools/image_to_pdf.py) is the script to covert images to PDFs for those models who take only PDFs as input.


<details>
  <summary>Dataset Format</summary>

The dataset format is JSON, with the following structure and field explanations:

```json
[{
    "layout_dets": [    // List of page elements
        {
            "category_type": "text_block",  // Category name
            "poly": [
                136.0, // Position information, coordinates for top-left, top-right, bottom-right, bottom-left corners (x,y)
                781.0,
                340.0,
                781.0,
                340.0,
                806.0,
                136.0,
                806.0
            ],
            "ignore": false,        // Whether to ignore during evaluation
            "order": 0,             // Reading order
            "anno_id": 0,           // Special annotation ID, unique for each layout box
            "text": "xxx",          // Optional field, Text OCR results are written here
            "latex": "$xxx$",       // Optional field, LaTeX for formulas and tables is written here
            "html": "xxx",          // Optional field, HTML for tables is written here
            "attribute" {"xxx": "xxx"},         // Classification attributes for layout, detailed below
            "line_with_spans:": [   // Span level annotation boxes
                {
                    "category_type": "text_span",
                    "poly": [...],
                    "ignore": false,
                    "text": "xxx",   
                    "latex": "$xxx$",
                 },
                 ...
            ],
            "merge_list": [    // Only present in annotation boxes with merge relationships, merge logic depends on whether single line break separated paragraphs exist, like list types
                {
                    "category_type": "text_block", 
                    "poly": [...],
                    ...   // Same fields as block level annotations
                    "line_with_spans": [...]
                    ...
                 },
                 ...
            ]
        ...
    ],
    "page_info": {         
        "page_no": 0,            // Page number
        "height": 1684,          // Page height
        "width": 1200,           // Page width
        "image_path": "xx/xx/",  // Annotated page filename
        "page_attribute": {"xxx": "xxx"}     // Page attribute labels
    },
    "extra": {
        "relation": [ // Related annotations
            {  
                "source_anno_id": 1,
                "target_anno_id": 2, 
                "relation": "parent_son"  // Relationship label between figure/table and their corresponding caption/footnote categories
            },
            {  
                "source_anno_id": 5,
                "target_anno_id": 6,
                "relation_type": "truncated"  // Paragraph truncation relationship label due to layout reasons, will be concatenated and evaluated as one paragraph during evaluation
            },
        ]
    }
},
...
]
```

</details>

<details>
  <summary>Evaluation Categories</summary>

Evaluation categories include:

```
# Block level annotation boxes (28 category_type values in v1.6 full release)
'title'                          # Title
'text_block'                     # Paragraph level plain text
'list_group'                     # List group
'reference'                      # References
'figure'                         # Figure
'figure_caption'                 # Figure caption / title
'figure_footnote'                # Figure note
'table'                          # Table body
'table_caption'                  # Table caption / title
'table_footnote'                 # Table footnote
'equation_isolated'              # Display formula
'equation_caption'               # Formula number / tag
'equation_semantic'              # Semantic formula region
'equation_explanation'           # Formula explanation / derivation-like text
'header'                         # Header
'footer'                         # Footer
'page_number'                    # Page number
'page_footnote'                  # Page footnote
'abandon'                        # Discarded / irrelevant regions
'code_txt'                       # Code block
'code_txt_caption'               # Code caption
'chart_mask'                     # Chart region to mask
'table_mask'                     # Table region to mask
'text_mask'                      # Text region to mask
'organic_chemical_formula_mask'  # Organic chemistry structure mask
'algorithm_mask'                 # Algorithm / pseudocode mask
'unknown_mask'                   # Other mask class
'need_mask'                      # Region requiring masking / pending mask class

# Span level annotation boxes
'text_span'           # Span level plain text
'equation_ignore',    # Formula to be ignored
'equation_inline',    # Inline formula
'footnote_mark',      # Document superscripts/subscripts
```

</details>

<details>
  <summary>Attribute Labels</summary>

Page classification attributes include:

```
'data_source': #PDF type classification
    academic_literature  # Academic literature
    PPT2PDF # PPT to PDF
    book # Black and white books and textbooks
    colorful_textbook # Colorful textbooks with images
    exam_paper # Exam papers
    note # Handwritten notes
    magazine # Magazines
    research_report # Research reports and financial reports
    newspaper # Newspapers
    historical_document # Historical documents

'language': #Language type (page attribute values)
    english # English
    simplified_chinese # Simplified Chinese
    en_ch_mixed # English-Chinese mixed
    traditional_chinese # Traditional Chinese
    other # Other

'layout': #Page layout type
    single_column # Single column
    double_column # Double column
    three_column # Three column
    1andmore_column # One mixed with multiple columns, common in literature
    other_layout # Other layouts

'watermark': # Whether contains watermark
    true  
    false

'fuzzy_scan': # Whether blurry scanned
    true  
    false

'colorful_backgroud': # Whether contains colorful background, content to be recognized has more than two background colors
    true  
    false
```

Block level attribute - Table related attributes:

```
'table_layout': # Table orientation
    vertical # Vertical table
    horizontal # Horizontal table

'with_span': # Merged cells
    False
    True

'line': # Table borders
    full_line # Full borders
    less_line # Partial borders
    fewer_line # Three-line borders
    wireless_line # No borders

'language': # Table language
    table_en # English table
    table_simplified_chinese # Simplified Chinese table
    table_en_ch_mixed # English-Chinese mixed table

'include_equation': # Whether table contains formulas
    False
    True

'include_backgroud': # Whether table contains background color
    False
    True

'table_vertical' # Whether table is rotated 90 or 270 degrees
    False
    True
```

Block level attribute - Text paragraph related attributes:

```
'text_language': # Text language
    text_en  # English
    text_simplified_chinese # Simplified Chinese
    text_en_ch_mixed  # English-Chinese mixed

'text_background':  # Text background color
    white # Default value, white background
    single_colored # Single background color other than white
    multi_colored  # Multiple background colors

'text_rotate': # Text rotation classification within paragraphs
    normal # Default value, horizontal text, no rotation
    rotate90  # Rotation angle, 90 degrees clockwise
    rotate180 # 180 degrees clockwise
    rotate270 # 270 degrees clockwise
    horizontal # Text is normal but layout is vertical
```

Block level attribute - Formula related attributes:

```
'formula_type': # Formula type
    print  # Print
    handwriting # Handwriting
    equation_en  # English formula
    equation_ch # Chinese formula
```

</details>


## Data Display
![](show_pdf_types_1.png)
![](show_pdf_types_2.png)

## Acknowledgement

- Thank [Abaka AI](https://abaka.ai) for supporting the dataset annotation.

## Copyright Statement

The PDFs are collected from public online channels and community user contributions. Content that is not allowed for distribution has been removed. The dataset is for research purposes only and not for commercial use. If there are any copyright concerns, please contact OpenDataLab@pjlab.org.cn.

## Citation

```bibtex
@misc{ouyang2024omnidocbenchbenchmarkingdiversepdf,
      title={OmniDocBench: Benchmarking Diverse PDF Document Parsing with Comprehensive Annotations}, 
      author={Linke Ouyang and Yuan Qu and Hongbin Zhou and Jiawei Zhu and Rui Zhang and Qunshu Lin and Bin Wang and Zhiyuan Zhao and Man Jiang and Xiaomeng Zhao and Jin Shi and Fan Wu and Pei Chu and Minghao Liu and Zhenxiang Li and Chao Xu and Bo Zhang and Botian Shi and Zhongying Tu and Conghui He},
      year={2024},
      eprint={2412.07626},
      archivePrefix={arXiv},
      primaryClass={cs.CV},
      url={https://arxiv.org/abs/2412.07626}, 
}
```

## Links

- Paper: https://huggingface.co/papers/2412.07626
- GitHub: https://github.com/opendatalab/OmniDocBench