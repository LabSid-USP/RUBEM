<!-- PROJECT SHIELDS -->
[![Documentation Status][readthedocs-shield]][readthedocs-url]
[![Contributors][contributors-shield]][contributors-url]
[![GitHub Commit Activity][commit-activity-shield]][commit-activity-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![LabSid YouTube Channel][youtube-shield]][youtube-url]
<!-- [![GPL v3 License][license-shield]][license-url] -->

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

The Rainfall rUnoff Balance Enhanced Model (RUBEM) is a hydrological model for transforming precipitation into surface and subsurface runoff. The model is based on equations that represent the physical processes of the hydrological cycle, with spatial distribution defined by pixel, in distinct vegetated and non-vegetated covers, and has the flexibility to study a wide range of applications, including impacts of changes in climate and land use, has flexible spatial resolution, the inputs are raster-type matrix files obtained from remote sensing data and operates with a reduced number of parameters arranged in a configuration file that facilitates its modification throughout the area.

### Main features

The model was developed based on classical concepts of hydrological processes and equations based mainly on SPHY (TERINK et al., 2015), WEAP (YATES et al., 2005), and WetSpass-M (ABDOLLAHI et al. , 2017). The main features of the developed model are:

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

* From Miniconda base envionment create a new conda envionment
   ```sh
   conda create --name rubem python=3.7
   ```
 * Activate the new environment

    Windows

     ```powershell
     conda activate rubem
     ```
    
    Linux, macOS
   
     ```sh
     source activate rubem
     ```
  
  * Install GDAL conda package
 
     ```sh
     conda install -c conda-forge gdal 
     ```
 
 * Install PCRaster conda package
 
   ```sh
   conda install -c conda-forge pcraster 
   ```

### Installation

1. Download the latest release zip file from the [releases page](https://github.com/LabSid-USP/RUBEM/releases);
2. Extract the zip, and copy the extracted root directory into a local directory.


<!-- USAGE EXAMPLES -->
## Usage

 * Typical usage example
   ```sh
   python rubem.py --configfile config.ini
   ```
 * Help usage example
   ```sh
   python rubem.py -h
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

Distributed under the GPLv3 License. See [`LICENSE.md`](https://github.com/LabSid-USP/RUBEM/blob/main/LICENSE.md) for more information.

<!-- CONTACT -->
## Contact

In any of our communication channels please abide by the [RUBEM Code of Conduct](https://github.com/LabSid-USP/RUBEM). In summary, being friendly and patient, considerate, respectful, and careful in your choice of words.

- Contact us at: [rubem.hydrological@labsid.eng.br](mailto:rubem.hydrological@labsid.eng.br)

- Support Form: [https://forms.gle/JmxWKoXh4C29V2rD8](https://forms.gle/JmxWKoXh4C29V2rD8)

- Project Link: [https://github.com/LabSid-USP/RUBEM](https://github.com/LabSid-USP/RUBEMHydrological)


<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements

* [Laboratório de Sistemas de Suporte a Decisões Aplicados à Engenharia Ambiental e de Recursos Hídricos](http://labsid.eng.br/Contato.aspx)
* [Departamento de Engenharia Hidráulica e Ambiental da Escola Politécnica da Universidade de São Paulo](http://www.pha.poli.usp.br/)
* [Fundo Patrimonial Amigos da Poli](https://www.amigosdapoli.com.br/)

<!-- MARKDOWN LINKS & IMAGES -->
[readthedocs-shield]: https://readthedocs.org/projects/rubem/badge/?version=latest
[readthedocs-url]: https://rubem.readthedocs.io/en/latest/?badge=latest
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
[license-url]: https://github.com/LabSid-USP/RUBEM/blob/master/LICENSE.md
[youtube-shield]: https://img.shields.io/youtube/channel/subscribers/UCZOGKRCW5mQOY9_w8L7lKJg
[youtube-url]: https://www.youtube.com/user/labsidengbr
