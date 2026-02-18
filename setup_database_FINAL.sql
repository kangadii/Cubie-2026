-- ============================================
-- FINAL Database Setup Script for CubieHelp
-- Uses OID (the actual primary key column)
-- ============================================

PRINT '=== Step 1: Checking UserProfile table ==='
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'UserProfile')
BEGIN
    PRINT '✗ ERROR: UserProfile table does not exist!'
    RAISERROR('UserProfile table not found', 16, 1)
    RETURN
END
PRINT '✓ UserProfile table exists'
GO

-- Step 2: Drop existing UserCredentials table if it exists
PRINT ''
PRINT '=== Step 2: Cleaning up existing UserCredentials table ==='
IF EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'UserCredentials')
BEGIN
    PRINT 'Dropping existing UserCredentials table...'
    DROP TABLE UserCredentials
    PRINT '✓ Existing table dropped'
END
ELSE
BEGIN
    PRINT 'No existing UserCredentials table found'
END
GO

-- Step 3: Create UserCredentials table
PRINT ''
PRINT '=== Step 3: Creating UserCredentials table ==='
CREATE TABLE UserCredentials (
    CredentialID INT IDENTITY(1,1) PRIMARY KEY,
    OID BIGINT NOT NULL UNIQUE,
    PasswordHash VARCHAR(255) NOT NULL,
    LastLogin DATETIME NULL,
    CreatedDate DATETIME NOT NULL DEFAULT GETDATE(),
    ModifiedDate DATETIME NULL,
    
    -- Foreign key to existing UserProfile table  
    CONSTRAINT FK_UserCredentials_UserProfile 
        FOREIGN KEY (OID) 
        REFERENCES UserProfile(OID)
        ON DELETE CASCADE
)

-- Create index for faster lookups
CREATE INDEX IX_UserCredentials_OID ON UserCredentials(OID)

PRINT '✓ UserCredentials table created successfully'
GO

-- Step 4: Find and insert credentials for TCube360
PRINT ''
PRINT '=== Step 4: Creating credentials for TCube360 ==='
DECLARE @OID BIGINT

SELECT @OID = OID 
FROM UserProfile 
WHERE UserName = 'TCube360'

IF @OID IS NULL
BEGIN
    PRINT '⚠ WARNING: User "TCube360" not found in UserProfile table'
    PRINT ''
    PRINT 'Existing users in your database:'
    SELECT TOP 10 OID, UserName, EmailId FROM UserProfile
    PRINT ''
    PRINT 'Please do ONE of the following:'
    PRINT '1. Create user TCube360 in UserProfile table first'
    PRINT '2. OR modify this script to use an existing username'
    PRINT ''
END
ELSE
BEGIN
    PRINT '✓ Found user TCube360 with OID: ' + CAST(@OID AS VARCHAR)
    
    -- Insert credentials
    INSERT INTO UserCredentials (OID, PasswordHash, LastLogin, CreatedDate)
    VALUES (
        @OID,
        '$2b$12$6SY/tc9bX.zGuzGceQHaQZbFXmlPfAdc',  -- Password: Cubie@2025
        GETDATE(),
        GETDATE()
    )
    
    PRINT '✓ Credentials created successfully'
    
    -- Verify
    PRINT ''
    PRINT '=== Step 5: Verification ==='
    SELECT 
        up.OID,
        up.UserName,
        up.EmailId,
        LEFT(uc.PasswordHash, 30) + '...' AS 'PasswordHash_Preview',
        uc.CreatedDate,
        uc.LastLogin
    FROM UserProfile up
    INNER JOIN UserCredentials uc ON up.OID = uc.OID
    WHERE up.UserName = 'TCube360'
    
    PRINT ''
    PRINT '=========================================='
    PRINT '✓✓✓ SETUP COMPLETE! ✓✓✓'
    PRINT '=========================================='
    PRINT 'You can now log in with:'
    PRINT '  Username: TCube360'
    PRINT '  Password: Cubie@2025'
    PRINT ''
    PRINT 'Visit: http://localhost:8000'
    PRINT '=========================================='
END
GO
