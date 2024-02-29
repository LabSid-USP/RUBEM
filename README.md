<!-- PROJECT SHIELDS -->
[![DOI][zenodo-shield]][zenodo-url]
[![GPL v3 License][license-shield]][license-url]
[![Unit tests][github-actions-unit-tests-shield]][github-actions-unit-tests-url]
[![CodeQL][github-actions-codeql-shield]][github-actions-codeql-url]
[![Documentation Status][readthedocs-shield]][readthedocs-url]
[![Issues][issues-shield]][issues-url]
[![Contributors][contributors-shield]][contributors-url]
[![GitHub Commit Activity][commit-activity-shield]][commit-activity-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![LabSid YouTube Channel][youtube-shield]][youtube-url]


<!-- PROJECT LOGO -->
<br />
<p align="center">
  <a href="https://github.com/LabSid-USP/RUBEM">
    <img src="doc/source/_static/icon.png" alt="Logo" width="120" height="120">
  </a>
  <h1 align="center">RUBEM<br>Rainfall rUnoff Balance Enhanced Model</br></h1>
  <p align="center">
    RUBEM is a distributed hydrological model to calculate monthly flows with changes in land use over time.
    <br />
    <a href="https://rubem.readthedocs.io/en/latest"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://forms.gle/JmxWKoXh4C29V2rD8">Support Form</a>
    ·
    <a href="https://github.com/LabSid-USP/RUBEM/issues">Report Bug</a>
    ·
    <a href="https://github.com/LabSid-USP/RUBEM/issues">Request Feature</a>
  </p>
</p>



<!-- TABLE OF CONTENTS -->
<details open="open">
  <summary><h2 style="display: inline-block">Table of Contents</h2></summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#main-features">Main features</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgements">Acknowledgements</a></li>
  </ol>
</details>


<!-- ABOUT THE PROJECT -->
## About The Project

The Rainfall rUnoff Balance Enhanced Model (RUBEM) [^MELLOetal2022a][^MELLOetal2022b] is a hydrological model for transforming precipitation into surface and subsurface runoff. The model is based on equations that represent the physical processes of the hydrological cycle, with spatial distribution defined by pixel, in distinct vegetated and non-vegetated covers, and has the flexibility to study a wide range of applications, including impacts of changes in climate and land use, has flexible spatial resolution, the inputs are raster-type matrix files obtained from remote sensing data and operates with a reduced number of parameters arranged in a configuration file that facilitates its modification throughout the area.

### Main features

The model was developed based on classical concepts of hydrological processes and equations based mainly on SPHY [^TERINKetal2015], WEAP [^YATESetal2005], and WetSpass-M [^ABDOLLAHIetal2017]. The main features of the developed model are:

- Distributed monthly step model;
- Hydrological process based on soil water balance in each pixel, and flow total calculated after composition of the resulting accumulated flow, according to Direction drainage network flow established by the digital elevation model (DEM);
- Calculations for two zones: rootzone and saturated;
- Evapotranspiration and interception process based on vegetation index: Leaf Area Index (LAI), Photosynthetically Active Radiation Fraction (FPAR) and Normalized Difference Vegetation Index (NDVI); and
- Sub-pixel level coverage classification, represented by four fractions that represent percentage of total pixel area covered exclusively by: area vegetated, bare soil area, water area and impervious area.

<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple steps.

### Prerequisites

This is an example of how to list things you need to use the software and how to install them.

- From Miniconda base envionment create a new conda envionment

   ```sh
   conda env create -n rubem --file env-prod.yml
   ```

 - Activate the new environment

    Windows

     ```powershell
     conda activate rubem
     ```
    
    Linux, macOS
   
     ```sh
     source activate rubem
     ```

### Installation

1. Download the latest release zip file from the [releases page](https://github.com/LabSid-USP/RUBEM/releases);
2. Extract the zip, and copy the extracted root directory into a local directory.


<!-- USAGE EXAMPLES -->
## Usage

 - Typical usage example
 
    ```sh
      python rubem --configfile config.ini
    ```

 - Help usage example

   ```sh
   python rubem -h
   ```   

_For more examples, please refer to the [Documentation](https://rubem.readthedocs.io/en/latest)_.

<!-- ROADMAP -->
## Roadmap

See the [open issues](https://github.com/LabSid-USP/RUBEM/issues) for a list of proposed features (and known issues).


<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**. See [`CONTRIBUTING.md`](https://github.com/LabSid-USP/RUBEM/blob/main/CONTRIBUTING.md) for more information.

<!-- LICENSE -->
## License

Distributed under the GPLv3 License. See [`LICENSE.md`](https://github.com/LabSid-USP/RUBEM/blob/main/LICENSE) for more information.

<!-- CONTACT -->
## Contact

> [!TIP]
> In any of our communication channels please abide by the [Code of Conduct](https://github.com/LabSid-USP/.github/blob/main/CODE_OF_CONDUCT.md#code-of-conduct). In summary, being friendly and patient, considerate, respectful, and careful in your choice of words.

- Contact us at: [rubem.hydrological@labsid.eng.br](mailto:rubem.hydrological@labsid.eng.br)
- Support Form: [https://forms.gle/JmxWKoXh4C29V2rD8](https://forms.gle/JmxWKoXh4C29V2rD8)
- Project Link: [https://github.com/LabSid-USP/RUBEM](https://github.com/LabSid-USP/RUBEMHydrological)

<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements

- [Laboratório de Sistemas de Suporte a Decisões Aplicados à Engenharia Ambiental e de Recursos Hídricos](https://labsid.poli.usp.br/)
- [Departamento de Engenharia Hidráulica e Ambiental da Escola Politécnica da Universidade de São Paulo](http://www.pha.poli.usp.br/)
- [Fundo Patrimonial Amigos da Poli](https://www.amigosdapoli.com.br/)

<!-- MARKDOWN LINKS & IMAGES -->
[zenodo-shield]: https://zenodo.org/badge/DOI/10.5281/zenodo.10562516.svg
[zenodo-url]: https://doi.org/10.5281/zenodo.10562516
[readthedocs-shield]: https://readthedocs.org/projects/rubem/badge/?version=latest
[readthedocs-url]: https://rubem.readthedocs.io/en/latest/?badge=latest
[github-actions-unit-tests-shield]: https://github.com/LabSid-USP/RUBEM/actions/workflows/build-test-micromamba.yml/badge.svg
[github-actions-unit-tests-url]: https://github.com/LabSid-USP/RUBEM/actions/workflows/build-test-micromamba.yml
[github-actions-codeql-shield]: https://github.com/LabSid-USP/RUBEM/actions/workflows/codeql-analysis.yml/badge.svg
[github-actions-codeql-url]: https://github.com/LabSid-USP/RUBEM/actions/workflows/codeql-analysis.yml
[contributors-shield]: https://img.shields.io/github/contributors/LabSid-USP/RUBEM
[contributors-url]: https://github.com/LabSid-USP/RUBEM/graphs/contributors
[commit-activity-shield]: https://img.shields.io/github/commit-activity/m/LabSid-USP/RUBEM
[commit-activity-url]: https://github.com/LabSid-USP/RUBEM/pulse
[forks-shield]: https://img.shields.io/github/forks/LabSid-USP/RUBEM
[forks-url]: https://github.com/LabSid-USP/RUBEM/network/members
[stars-shield]: https://img.shields.io/github/stars/LabSid-USP/RUBEM
[stars-url]: https://github.com/LabSid-USP/RUBEM/stargazers
[issues-shield]: https://img.shields.io/github/issues/LabSid-USP/RUBEM
[issues-url]: https://github.com/LabSid-USP/RUBEM/issues
[license-shield]: https://img.shields.io/github/license/LabSid-USP/RUBEM
[license-url]: https://github.com/LabSid-USP/RUBEM/blob/master/LICENSE
[youtube-shield]: https://img.shields.io/youtube/channel/subscribers/UCZOGKRCW5mQOY9_w8L7lKJg
[youtube-url]: https://www.youtube.com/user/labsidengbr

<!-- MARKDOWN REFERENCES -->
[^ABDOLLAHIetal2017]: Abdollahi, K., Bashir, I., Harouna, M., Griensven, A., Huysmans, M., Batelaan, O., Verbeiren, B., A distributed monthly water balance model: formulation and application on Black Volta Basin, Environ Earth Sci, 76:198, 2017. https://doi.org/10.1007/s12665-017-6512-1
[^MELLOetal2022a]: Méllo Júnior, A.V.; Olivos, L.M.O.; Billerbeck, C.; Marcellini, S.S.; Vichete, W.D.; Pasetti, D.M.; da Silva, L.M.; Soares, G.A.d.S.; Tercini, J.R.B. Rainfall Runoff Balance Enhanced Model Applied to Tropical Hydrology. Water 2022, 14, 1958. https://doi.org/10.3390/w14121958
[^MELLOetal2022b]: Méllo Júnior, A.V.; Olivos, L.M.O.; Billerbeck, C.; Marcellini, S.S.; Vichete, W.D.; Pasetti, D.M.; da Silva, L.M.; Soares, G.A.d.S.; Tercini, J.R.B. Rainfall-Runoff Balance Enhanced Model Applied to Tropical Hydrology - Supplementary Document. Zenodo 2022. https://doi.org/10.5281/zenodo.6614981
[^TERINKetal2015]: Terink, W., Lutz, A. F., Simons, G. W. H., Immerzeel, W. W., & Droogers, P. (2015). SPHY v2.0: Spatial Processes in HYdrology. Geoscientific Model Development, 8(7), 2009–2034. https://doi.org/10.5194/gmd-8-2009-2015
[^YATESetal2005]: Yates, D., Sieber, J., Purkey, D., & Huber-Lee, A. (2005). WEAP21—A Demand-, Priority-, and Preference-Driven Water Planning Model. Water International, 30(4), 487–500. https://doi.org/10.1080/02508060508691893