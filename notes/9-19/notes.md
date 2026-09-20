Current pose estimation strategy:
        poseEstimator = new PhotonPoseEstimator(
                AprilTags.getAprilTagFieldLayout(), PoseStrategy.MULTI_TAG_PNP_ON_COPROCESSOR, this.robotToCamera);
        poseEstimator.setTagModel(TargetModel.kAprilTag36h11);
        poseEstimator.setMultiTagFallbackStrategy(PoseStrategy.LOWEST_AMBIGUITY);


New pose estimation strategy:
    poseEstimator = new PhotonPoseEstimator(
        AprilTags.getAprilTagFieldLayout(), PoseStrategy.MULTI_TAG_PNP_ON_RIO, this.robotToCamera);


recorded: akit_26-09-19_15-29-36_MULTI_TAG_PNP_ON_RIO.wpilog


change to lowest ambiguity:
        poseEstimator = new PhotonPoseEstimator(
                AprilTags.getAprilTagFieldLayout(), PoseStrategy.LOWEST_AMBIGUITY, this.robotToCamera);
        poseEstimator.setTagModel(TargetModel.kAprilTag36h11);
        poseEstimator.setMultiTagFallbackStrategy(PoseStrategy.LOWEST_AMBIGUITY);

recorded: 