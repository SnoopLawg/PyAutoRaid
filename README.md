<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a name="readme-top"></a>
<!--
*** Thanks for checking out the Best-README-Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Don't forget to give the project a star!
*** Thanks again! Now go create something AMAZING! :D
-->



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
Total downloads: 1634
--- 
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]




<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/SnoopLawg/PyAutoRaid">
    <img src="https://user-images.githubusercontent.com/30202466/181846024-930b7120-0af6-4280-b727-87bdd4ade7b8.jpeg" alt="Logo">
  </a>

<h3 align="center">PyAutoRaid</h3>

  <p align="center">
    I am trying to automate Raid: Shadow Legends  without accessing game data but using pyautogui and finding images on the game's screen. I wish to do it with gamedata but I do not know how, and I know autoclickers are allowed in RSL so this is my novice attempt at it.
    <br />
    <!--<a href="https://github.com/SnoopLawg/PyAutoRaid"><strong>Explore the docs »</strong></a>-->
    <br />
    <br />
    <a href="https://github.com/SnoopLawg/PyAutoRaid">View Code</a>
    ·
    <a href="https://github.com/SnoopLawg/PyAutoRaid/issues">Report Bug</a>
    ·
    <a href="https://github.com/SnoopLawg/PyAutoRaid/issues">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
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
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project
<!--
[![Product Name Screen Shot][Exe, GUI Interface, and Raid]](https://user-images.githubusercontent.com/30202466/235019154-2fb0524d-bddc-4a16-833a-ffc9c6d115bc.png)

Here's a blank template to get started: To avoid retyping too much info. Do a search and replace with your text editor for the following: `github_username`, `repo_name`, `twitter_handle`, `linkedin_username`, `email_client`, `email`, `project_title`, `project_description`
-->
<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)



<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

Download the newest release of DailyQuests.exe and PyautoRaid.exe. It was created with "Windows Task Scheduler" in mind. You can click the app manually and it will run through and  Collect your rewards like gems and upgrade in the sparring pit, and fight some battles in classicand campaign. The purpose though is for the app to run on its own, so "Windows Task Scheduler" is pre-built in Windows and can run your downloaded exe file every so often if you please.


### Prerequisites

Must be on a Windows Computer.<br> 
Tested on:<br>
* Windows 10
* 1920 x 1080 Monitor

### Installation

1. [CLICK HERE](https://github.com/SnoopLawg/PyAutoRaid/releases/download/v2.1-beta/PARinstaller.exe) to download both PyAutoRaid.exe and DailyQuests.exe<br>
2. Click through the installer. Once finished, make sure your antivirus will allow you run them :).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

##### DailyQuests.exe 
Watch this video for a comprehensive introduction. [CLICK HERE](https://youtu.be/FOaXg9hXk3s )
  - Double click DailyQuests.exe in your downloads folder to start it. (it may take a second to open raid) 
  - The "GUI Interface" should show up and then raid begins to open. Nothing else needs to be touched unless it is your first time using the application, in which you should click the boxes of what Tasks you want to run. 
  - If you do not want it to run automatically, go to your DQconfig.ini file and change the automated to equal False
  - If you have manual off, you can do manual runs

______________________________________________________________________________________________________________________________
##### Windows Task Scheduler
This is needed if you want the app to run every hour.

1. Open "Windows Task Scheduler"
2. Click "Create Task" on the top right
3. Name it whatever you want (doesnt matter)
4. Click "Run with Hightest Privileges"
5. Click "Triggers", then "New".., and then select whatever you want. (however often you want it to run. I run it "Daily" , and I set the start to be todays date and the top of the next hour. I then click the "Repeat task every hour""
6. Click OK
7. Click "Actions", then "New...", "Browse...", and then find the exe file wherever you placed it.
8. Click OK
9. This should now run the app however often you set it in Windows Task Scheduler. You can test to see if it works by clicking on your task under the Task Scheduler Library Folder on the top left, and clicking Run on the far right side.

_For more examples, please refer to the ![Step-by-Step-Video]([https://example.com](https://img.youtube.com/vi/YOUTUBE_VIDEO_ID_HERE/0.jpg)](https://www.veed.io/view/975c29ce-a472-4b2a-acfa-7b22edb42753?sharingWidget=true&panel=share))_

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

- [ ] Make it so the mouse isn't taken control of entirely.
- [x] Collect/Do Daily quests ??
- [ ] Click and do game events without mouse entirely
    - [ ] Need to remove Image recognition and get game data instead.

See the [open issues](https://github.com/github_username/repo_name/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- LICENSE -->
## License

No License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Project Link: [https://github.com/SnoopLawg/PyAutoRaid](https://github.com/SnoopLawg/PyAutoRaid)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [SnoopLawg](https://github.com/SnoopLawg)
* [Raid](https://plarium.com/landings/en/desktop/raid/rdo/cro/cave_f002p_a_m_jt2180_v1?plid=1031237&pxl=google_search&publisherid=raid%20shadow%20legends_kwd-828443951496_143343244765&placement=643747462252_143343244765&adpartnerset=143343244765&gad=1&gclid=CjwKCAjwuqiiBhBtEiwATgvixKqwMslbeEV2CreSpaOkwCs8Wk0CwqZOKILvnYzQL2KYciqV4-wZExoCI6MQAvD_BwE) for not being free-to-play friendly for a busy man

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/SnoopLawg/PyAutoRaid.svg?style=for-the-badge
[contributors-url]: https://github.com/SnoopLawg/PyAutoRaid/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/SnoopLawg/PyAutoRaid.svg?style=for-the-badge
[forks-url]: https://github.com/SnoopLawg/PyAutoRaid/network/members
[stars-shield]: https://img.shields.io/github/stars/SnoopLawg/PyAutoRaid.svg?style=for-the-badge
[stars-url]: https://github.com/SnoopLawg/PyAutoRaid/stargazers
[issues-shield]: https://img.shields.io/github/issues/SnoopLawg/PyAutoRaid.svg?style=for-the-badge
[issues-url]: https://github.com/SnoopLawg/PyAutoRaid/issues
[license-shield]: https://img.shields.io/github/license/SnoopLawg/PyAutoRaid.svg?style=for-the-badge
[license-url]: https://github.com/SnoopLawg/PyAutoRaid/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/linkedin_username
[product-screenshot]: images/screenshot.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/

<!--  
# PyAutoRaid
![raid-header](https://user-images.githubusercontent.com/30202466/181846024-930b7120-0af6-4280-b727-87bdd4ade7b8.jpeg)

[![Step-by-Step Video Download Guide](https://img.youtube.com/vi/YOUTUBE_VIDEO_ID_HERE/0.jpg)](https://www.veed.io/view/975c29ce-a472-4b2a-acfa-7b22edb42753?sharingWidget=true&panel=share)

### How to Use
1. Download Main.exe
[DOWNLOADE HERE](https://github.com/SnoopLawg/PyAutoRaid/releases/download/v1.5-beta/Main.exe)<br>
(You can now run it by clicking it)


###### optional:<br>
  Make the app run incrementally:

2. Open "Windows Task Scheduler"
3. Click "Create Task" on the top right
4. Name it whatever you want (doesnt matter)
5. Click "Run with Hightest Privileges"
6. Click "Triggers", then "New".., and then select whatever you want. (however often you want it to run. I run it "Daily" , and I set the start to be todays date and the top of the next hour. I then click the "Repeat task every hour""
7. Click OK
8. Click "Actions", then "New...", "Browse...", and then find the exe file wherever you placed it.
9. Click OK
10. This should now run the app however often you set it in Windows Task Scheduler. You can test to see if it works by clicking on your task under the Task Scheduler Library Folder on the top left, and clicking Run on the far right side.

When running the program for the first time be sure to make your changes then submit on the gui.

### Technical
I am trying to automate Raid: Shadow Legends  without accessing game data but using pyautogui and finding images on the game's screen. I wish to do it with gamedata but I do not know how, and I know autoclickers are allowed in RSL so this is my novice attempt at it.
- [x] CheckIfFileExists()<br>
      -Checks if you have the correct files
- [x] OpenRaid()<br>
      -Starts and awaits raid to open
- [x] AutoRewards()<br>
      -Collects Gem Mine, Daily quests, Advanced Quests, Inbox, Upgrades champions in autoupgrade thing, and buys mystery and ancient shards from market.
- [x] AutoCB()<br>
      -My FAVORITE (and reason I made this app). Attacks clan boss depending on what you set in your GUI. If met the number of battles (Ex. 2/2 UNM fights) it will move on to the next difficulty. If you completed all fights you need (you put in the gui) it will default to UNM fighting.
- [x] ClassicArena()<br>
      -Battles 10 times or until out of coins. Will also buy Drexthar Bloodtwin if not yet purchased
- [x] quitAll()<br>
      -Quits out of everything including Raid, Plarium and this app.
- [x] BlackOutMonitor()<br>
      -Blacks out your monitors without turning off your computer. (I use this so I can run this like every hour and not have my monitors on always)
- [x] TagTeamArena()<br>
      -Battles 10 times or until out of coins
- [ ] AutoUpgrader<br>
      -Cannot control mouseclicks when I run RSLHELPER by farbstoff... so I would have to get gamedata. (NEED HELP!!)
- [x] Gui<br>
      -Gui popup to manage what you want to run
- [x] Exe file for all of this<br>
      -PyAutoRaid.exe created

-->
