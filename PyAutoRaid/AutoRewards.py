#Retrieve all rewards at Bastion
import pyautogui
import time
from LoopFindImage import LoopFindImage

def AutoRewards():
    time.sleep(10)
    while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",confidence=0.8) ==None:
        with open("log.txt", mode='a') as file:
                file.write("\n deleting ads now")
    LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png","\n ad ")
    
    #Gem Mine
    pyautogui.click(579,684)
    time.sleep(2)
    pyautogui.hotkey('esc')  # esc gem mine
    time.sleep(2)
    LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png","\n ad closed ") #if gem mine empty closes the wuit window so doesnt quit
    time.sleep(1)
##    while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",confidence=0.8) !=None:
##        adx,ady=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",confidence=0.8)
##        pyautogui.click(adx,ady)
##        with open("log.txt", mode='a') as file:
##            file.write("\n ad closed")
##        time.sleep(2)
    while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\yesBTN.png",confidence=0.8) !=None:
        yesBTNx,yesBTNy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\yesBTN.png",confidence=0.8)
        pyautogui.click(yesBTNx,yesBTNy)
        with open("log.txt", mode='a') as file:
            file.write("\n yes button clicked")
        time.sleep(2)
        
    #MARKET - check for shards
    if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\theMarket.png",confidence=0.8):
        theMarketx,theMarkety=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\theMarket.png",confidence=0.8)
        pyautogui.click(theMarketx,theMarkety)
        with open("log.txt", mode='a') as file:
            file.write("\n shop clicked")
        time.sleep(2)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\shopShard.png",confidence=0.8) !=None:
            shopShardx,shopShardy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\shopShard.png",confidence=0.8)
            pyautogui.click(shopShardx,shopShardy)
            time.sleep(2)
            while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\getShard.png",confidence=0.8) !=None:
                shopShardx,shopShardy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\getShard.png",confidence=0.8)
                pyautogui.click(shopShardx,shopShardy)
                continue
            with open("log.txt", mode='a') as file:
                file.write("\n shard bought")
            time.sleep(2)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\marketAS.png",confidence=0.8) !=None:
            shopShardx,shopShardy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\marketAS.png",confidence=0.8)
            pyautogui.click(shopShardx,shopShardy)
            time.sleep(2)
            while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\getAS.png",confidence=0.8) !=None:
                shopShardx,shopShardy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\getAS.png",confidence=0.8)
                pyautogui.click(shopShardx,shopShardy)
                continue
            with open("log.txt", mode='a') as file:
                file.write("\n shard bought")
            time.sleep(2)
        LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png","\n back to Bastion x ")
        LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png","\n ad closed ")

            
    #SHOP - claim AS, claim MS, check offers for goodieBag,miniPack,smallPack,regularPack, then claim       
    if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\shopBTN.png",confidence=0.8) :
        shopBTNx,shopBTNy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\shopBTN.png",confidence=0.8)
        pyautogui.click(shopBTNx,shopBTNy)
        with open("log.txt", mode='a') as file:
            file.write("\n opening shop")
        time.sleep(2)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimAS.png",confidence=0.8) !=None:
            claimASx,claimASy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimAS.png",confidence=0.8)
            pyautogui.click(claimASx,claimASy)
            with open("log.txt", mode='a') as file:
                file.write("\n claiming Ancient Shard")
            time.sleep(2)
            while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\defaultClaim.png",confidence=0.8) !=None:
                defaultClaimx,defaultClaimy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\defaultClaim.png",confidence=0.8)
                pyautogui.click(defaultClaimx,defaultClaimy)
                with open("log.txt", mode='a') as file:
                    file.write("\n claimed")
                time.sleep(3)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimMS.png",confidence=0.8) !=None:
            claimMSx,claimMSy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimMS.png",confidence=0.8)
            pyautogui.click(claimMSx,claimMSy)
            with open("log.txt", mode='a') as file:
                file.write("\n claiming mystery Shard")
            time.sleep(3)
            while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\defaultClaim.png",confidence=0.8) !=None:
                defaultClaimx,defaultClaimy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\defaultClaim.png",confidence=0.8)
                pyautogui.click(defaultClaimx,defaultClaimy)
                with open("log.txt", mode='a') as file:
                    file.write("\n claimed")
                time.sleep(3)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\offers.png",confidence=0.9) !=None:
            offersx,offersy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\offers.png",confidence=0.8)
            pyautogui.click(offersx,offersy)
            time.sleep(3)
            if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goodieBag.png",confidence=0.8): 
                goodieBagx,goodieBagy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goodieBag.png",confidence=0.8)
                pyautogui.click(goodieBagx,goodieBagy)
                time.sleep(1)
            if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\miniPack.png",confidence=0.8): 
                goodieBagx,goodieBagy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\miniPack.png",confidence=0.8)
                pyautogui.click(goodieBagx,goodieBagy)
                time.sleep(1)
            if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\smallPack.png",confidence=0.8): 
                smallPackx,smallPacky=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\smallPack.png",confidence=0.8)
                pyautogui.click(smallPackx,smallPacky)
                time.sleep(1)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\regularPack.png","\n regualr pack claimed ")
            pyautogui.click(724,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n claiming free gift ")
            time.sleep(1)
            pyautogui.click(793,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n claiming free gift ")
            time.sleep(1.5)
            pyautogui.click(860,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n claiming free gift ")
            time.sleep(1.5)
            pyautogui.click(928,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n claiming free gift ")
            time.sleep(1.5)
            pyautogui.click(998,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n claiming free gift ")
            time.sleep(1.5)
            pyautogui.click(1072,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n claiming free gift ")
            time.sleep(1.5)
            pyautogui.click(1138,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n claiming free gift ")
            time.sleep(1.5)
            pyautogui.click(1207,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n claiming free gift ")
            time.sleep(1.5)
            pyautogui.click(1278,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n claiming free gift ")
            time.sleep(1.5)
            pyautogui.click(1351,333)
            LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png","\n regualr pack claimed ")
            time.sleep(1.5)
            #keep adding offers
            while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",confidence=0.8)!=None: 
                miniPackx,miniPacky=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\claimFreeGift.png",confidence=0.8)
                pyautogui.click(miniPackx,miniPacky)
                time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",confidence=0.8) !=None:
            goBackx,goBacky=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",confidence=0.8)
            pyautogui.click(goBackx,goBacky)
            with open("log.txt", mode='a') as file:
                file.write("\n Back to bastion")
            time.sleep(1)
        LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png","\n ad closed ")

    #GUARDIAN RING - Upgrade cgampions         
    if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\guardianRing.png",confidence=0.8):
        guardianRingx,guardianRingy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\guardianRing.png",confidence=0.8)
        pyautogui.click(guardianRingx,guardianRingy)
        with open("log.txt", mode='a') as file:
            file.write("\n open guardian ring")
        time.sleep(2)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\GRupgrade.png",confidence=0.8) !=None:
            GRupgradex,GRupgradey=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\GRupgrade.png",confidence=0.8)
            pyautogui.click(GRupgradex,GRupgradey)
            with open("log.txt", mode='a') as file:
                file.write("\n upgrading champions")
            time.sleep(2)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",confidence=0.8) !=None:
            goBackx,goBacky=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",confidence=0.8)
            pyautogui.click(goBackx,goBacky)
            with open("log.txt", mode='a') as file:
                file.write("\n Back to bastion")
            time.sleep(2)
        LoopFindImage(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png","\n ad closed ")
            
    #TIME REWARDS
    if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\timeRewards.png",confidence=0.8):
        timeRewardsx,timeRewardsy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\timeRewards.png",confidence=0.8)
        pyautogui.click(timeRewardsx,timeRewardsy)
        with open("log.txt", mode='a') as file:
            file.write("\n claiming timed rewards")
        time.sleep(2)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\5min.png",confidence=0.8) !=None:
            fiveminx,fiveminy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\5min.png",confidence=0.8)
            pyautogui.click(fiveminx,fiveminy)
            time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\20min.png",confidence=0.8) !=None:
            twentyminx,twentyminy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\20min.png",confidence=0.8)
            pyautogui.click(twentyminx,twentyminy)
            time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\40min.png",confidence=0.8) !=None:
            fortyminx,fortyminy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\40min.png",confidence=0.8)
            pyautogui.click(fortyminx,fortyminy)
            time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\60min.png",confidence=0.8) !=None:
            sixtyminx,sixtyminy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\60min.png",confidence=0.8)
            pyautogui.click(sixtyminx,sixtyminy)
            time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\90min.png",confidence=0.8) !=None:
            ninetyminx,ninetyminy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\90min.png",confidence=0.8)
            pyautogui.click(ninetyminx,ninetyminy)
            time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\180min.png",confidence=0.8) !=None:
            lastminx,lastminy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\180min.png",confidence=0.8)
            pyautogui.click(lastminx,lastminy)
            time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",confidence=0.8) !=None:
            adx,ady=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\exitAdd.png",confidence=0.8)
            pyautogui.click(adx,ady)
            with open("log.txt", mode='a') as file:
                file.write("\n ad closed")
            time.sleep(3)
            
    #CLAN - check in and claim rewards
    if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanBTN.png",confidence=0.8):
        clanBTNx,clanBTNy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanBTN.png",confidence=0.8)
        pyautogui.click(clanBTNx,clanBTNy)
        with open("log.txt", mode='a') as file:
            file.write("\n opening clan button")
        time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanMembers.png",confidence=0.8) !=None:
            clanMembersx,clanMembersy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanMembers.png",confidence=0.8)
            pyautogui.click(clanMembersx,clanMembersy)
            time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanCheckIn.png",confidence=0.8) !=None:
            clanCheckInx,clanCheckIny=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanCheckIn.png",confidence=0.8)
            pyautogui.click(clanCheckInx,clanCheckIny)
            time.sleep(1)
        if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanTreasure.png",confidence=0.8):
            clanTreasurex,clanTreasurey=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\clanTreasure.png",confidence=0.8)
            pyautogui.click(clanTreasurex,clanTreasurey)
            time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",confidence=0.8) !=None:
            goBackx,goBacky=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",confidence=0.8)
            pyautogui.click(goBackx,goBacky)
            with open("log.txt", mode='a') as file:
                file.write("\n Back to bastion")
            time.sleep(3)
            
    #QUESTS - Check for completed daily and advanced quests and claim
    if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\quests.png",confidence=0.8):
        questsx,questsy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\quests.png",confidence=0.8)
        pyautogui.click(questsx,questsy)
        with open("log.txt", mode='a') as file:
            file.write("\n opening quests button")
        time.sleep(2)  
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\questClaim.png",confidence=0.8) !=None:
            questClaimx,questClaimy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\questClaim.png",confidence=0.8)
            pyautogui.click(questClaimx,questClaimy)
            time.sleep(1)
        if pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\advancedQuests.png",confidence=0.8):
            advancedQuestsx,advancedQuestsy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\advancedQuests.png",confidence=0.8)
            pyautogui.click(advancedQuestsx,advancedQuestsy)
            time.sleep(1)
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\questClaim.png",confidence=0.8) !=None:
            questClaimx,questClaimy=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\questClaim.png",confidence=0.8)
            pyautogui.click(questClaimx,questClaimy)
            time.sleep(1) 
        while pyautogui.locateOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",confidence=0.8) !=None:
            goBackx,goBacky=pyautogui.locateCenterOnScreen(r"C:\\Users\\logan\\OneDrive\\Desktop\\AutoRaidAutomate\\PyAutoRaid\\assets\\goBack.png",confidence=0.8)
            pyautogui.click(goBackx,goBacky)
            with open("log.txt", mode='a') as file:
                file.write("\n Back to bastion")
            time.sleep(1)

if __name__=='__main__':
    AutoRewards()