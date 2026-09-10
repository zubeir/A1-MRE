graph TD
    %% Phase 1: Intake & Initial Review
    Start([1. Candidate Applies / Scanned QR]) --> HRReview[Candidate Status: HR Manager Review]
    HRReview --> HMStart[Candidate Status: HM Review start / Hiring Manager Review]

 graph TD

    %% Phase 1: Intake & Initial Review

    Start([1. Candidate Applies / Scanned QR]) --> HRReview[Candidate Status: HR Manager Review]

    HRReview --> HMStart[Candidate Status: HM Review start / Hiring Manager Review]

    

    %% Decision 1

    HMStart --> RejectCheck1{Pass Initial Review?}

    RejectCheck1 -- No --> StatusReject[Candidate Status: Rejected]

    RejectCheck1 -- Hold --> StatusBackup[Candidate Status: Keep as Backup]

    

    %% Phase 2: Interviewing

    RejectCheck1 -- Yes --> IntSched[Candidate Status: Interview Scheduling]

    IntSched --> IntBooked[Candidate Status: Interview Scheduled]

    IntBooked --> IntDone[Candidate Status: Interviewed]

    

    %% Decision 2

    IntDone --> RejectCheck2{Select Candidate?}

    RejectCheck2 -- No --> StatusReject

    RejectCheck2 -- Hold --> StatusBackup

    

    %% Phase 3: Offer Management

    RejectCheck2 -- Yes --> AppOffer[Candidate Status: Approved for offer]

    AppOffer --> OfferSub[Candidate Status: Offer Submitted]

    OfferSub --> OfferAcc[Candidate Status: Offer Accepted]

    

    %% Phase 4: Post-Offer Verification & Onboarding

    OfferAcc --> PostVerifInit[Candidate Status: Post Verification Initiated]

    PostVerifInit --> BGCheckInit[Candidate Status: Background Check Initiated]

    BGCheckInit --> BGCheckDone[Candidate Status: Background Checked]

    BGCheckDone --> PostVerifDone[Candidate Status: Post Verified]

    

    %% Phase 5: Ready for Shift

    PostVerifDone --> TransferredHR[Candidate Status: Transferred To Hr]

    TransferredHR --> ShiftReady([Worker Ready for Shift])   %% Decision 1
    HMStart --> RejectCheck1{Pass Initial Review?}
    RejectCheck1 -- No --> StatusReject[Candidate Status: Rejected]
    RejectCheck1 -- Hold --> StatusBackup[Candidate Status: Keep as Backup]

    %% Phase 2: Interviewing
    RejectCheck1 -- Yes --> IntSched[Candidate Status: Interview Scheduling]
    IntSched --> IntBooked[Candidate Status: Interview Scheduled]
    IntBooked --> IntDone[Candidate Status: Interviewed]

    %% Decision 2
    IntDone --> RejectCheck2{Select Candidate?}
    RejectCheck2 -- No --> StatusReject
    RejectCheck2 -- Hold --> StatusBackupgraph TD

    %% Phase 1: Intake & Initial Review

    Start([1. Candidate Applies / Scanned QR]) --> HRReview[Candidate Status: HR Manager Review]

    HRReview --> HMStart[Candidate Status: HM Review start / Hiring Manager Review]

    

    %% Decision 1

    HMStart --> RejectCheck1{Pass Initial Review?}

    RejectCheck1 -- No --> StatusReject[Candidate Status: Rejected]

    RejectCheck1 -- Hold --> StatusBackup[Candidate Status: Keep as Backup]

    

    %% Phase 2: Interviewing

    RejectCheck1 -- Yes --> IntSched[Candidate Status: Interview Scheduling]

    IntSched --> IntBooked[Candidate Status: Interview Scheduled]

    IntBooked --> IntDone[Candidate Status: Interviewed]

    

    %% Decision 2

    IntDone --> RejectCheck2{Select Candidate?}

    RejectCheck2 -- No --> StatusReject

    RejectCheck2 -- Hold --> StatusBackup

    

    %% Phase 3: Offer Management

    RejectCheck2 -- Yes --> AppOffer[Candidate Status: Approved for offer]

    AppOffer --> OfferSub[Candidate Status: Offer Submitted]

    OfferSub --> OfferAcc[Candidate Status: Offer Accepted]

    

    %% Phase 4: Post-Offer Verification & Onboarding

    OfferAcc --> PostVerifInit[Candidate Status: Post Verification Initiated]

    PostVerifInit --> BGCheckInit[Candidate Status: Background Check Initiated]

    BGCheckInit --> BGCheckDone[Candidate Status: Background Checked]

    BGCheckDone --> PostVerifDone[Candidate Status: Post Verified]

    

    %% Phase 5: Ready for Shift

    PostVerifDone --> TransferredHR[Candidate Status: Transferred To Hr]

    TransferredHR --> ShiftReady([Worker Ready for Shift])

    %% Phase 3: Offer Management
    RejectCheck2 -- Yes --> AppOffer[Candidate Status: Approved for offer]
    AppOffer --> OfferSub[Candidate Status: Offer Submitted]
    OfferSub --> OfferAcc[Candidate Status: Offer Accepted]

    %% Phase 4: Post-Offer Verification & Onboarding
    OfferAcc --> PostVerifInit[Candidate Status: Post Verification Initiated]
    PostVerifInit --> BGCheckInit[Candidate Status: Background Check Initiated]
    BGCheckInit --> BGCheckDone[Candidate Status: Background Checked]
    BGCheckDone --> PostVerifDone[Candidate Status: Post Verified]

    %% Phase 5: Ready for Shift
    PostVerifDone --> TransferredHR[Candidate Status: Transferred To Hr]
    TransferredHR --> ShiftReady([Worker Ready for Shift])
