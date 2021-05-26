<!-- PROJECT LOGO -->
<br />
<p align="center">
  <h1 align="center">RUBEM</h1>

  <p align="center">
    Rainfall rUnoff Balance Enhanced Model is a distributed hydrological model to calculate monthly flows with changes in land use over time
    <br />
    <a href="https://github.com/LabSid-USP/RUBEM"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/LabSid-USP/RUBEM">View Demo</a>
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
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#packaging">Packaging</a></li>
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

Rainfall rUnoff Balance Enhanced Model (RUBEM) is an improved model of balance between rain and runoff. The distributed hydrological model for transforming precipitation into total flow is based on equations that represent the physical processes of the hydrological cycle, with spatial distribution defined in a grid and monthly time scale. The model was developed based on classic concepts of hydrological processes and equations based mainly on the formulations of the SPHY (TERINK et al., 2015), WEAP (YATES et al., 2005) and WetSpass-M (ABDOLLAHI et al., 2017).

The name is a posthumous tribute to Professor Rubem La Laina Porto, dean of the Department of Hydraulic and Environmental Engineering, of the Polytechnic School of USP, who dedicated his professional life to the study, development and practices in hydrological sciences, contributing to the improvement of the state of art and training of students and professionals working in the area.

<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple steps.

### Prerequisites

This is an example of how to list things you need to use the software and how to install them.

* Create a conda envionment
```sh
  conda create --name rubem
 ```
 * Activate the new environment

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Windows
```powershell
  activate rubem
```
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Linux, macOS
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

Clone the repo
   ```sh
   git clone https://github.com/LabSid-USP/RUBEM.git
   ```
   
### Packaging

1. Clone the repo
   ```sh
   git clone https://github.com/LabSid-USP/RUBEM.git
   ```
2. Install PyInstaller conda package in another conda environment
   ```sh
    conda install -c conda-forge pyinstaller 
   ```   
3. Bundle this application and all its dependencies into a single package 
   ```sh
    pyinstaller -–onefile RainfallRunoff.py
   ```
   
<!-- USAGE EXAMPLES -->
## Usage

 * Typical usage example
   ```sh
   python RainfallRunoff.py --configfile config.ini
   ```
 * Help usage example
   ```sh
   python RainfallRunoff.py -h
   ```   

_For more examples, please refer to the [Documentation](https://example.com)_

<!-- ROADMAP -->
## Roadmap

See the [open issues](https://github.com/LabSid-USP/RUBEM/issues) for a list of proposed features (and known issues).


<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<!-- LICENSE -->
## License

Distributed under the GPLv3 License. See `LICENSE` for more information.

<!-- CONTACT -->
## Contact

Project Link: [https://github.com/LabSid-USP/RUBEM](https://github.com/LabSid-USP/RUBEM)

<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements

* [Laboratório de Sistemas de Suporte a Decisões Aplicados à Engenharia Ambiental e de Recursos Hídricos](http://labsid.eng.br/Contato.aspx)
* [Departamento de Engenharia Hidráulica e Ambiental da Escola Politécnica da Universidade de São Paulo](http://www.pha.poli.usp.br/)
* [Fundo Patrimonial Amigos da Poli](https://www.amigosdapoli.com.br/)
