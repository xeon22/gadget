
param ($groups, $users, $delim = ".", $domain = "capco.com")

$groupList = $groups.Split(',')
$userList = $users.Split(',')

function global:Get-Upn ($FirstName, $LastName) {
    return "${firstName}.${lastName}_${domain}#EXT#@catosaasdevelopment.onmicrosoft.com"
}

Connect-AzureAD
foreach ($element in $userList) {
    $name = $element.Split('@')[0]
    $firstName, $lastName = $name.Split($delim)
    New-AzureADMSInvitation -InvitedUserDisplayName "${firstName} ${lastName}" -InvitedUserEmailAddress $element -InviteRedirectUrl "https://portal.azure.com" -InvitedUserType "Guest" -SendInvitationMessage $true
    #Start-Sleep -Seconds 10

    $upn = Get-Upn -FirstName $firstName -LastName $lastName
    $user = Get-AzureADUser -Filter "userPrincipalName eq '${upn}'"
    
    foreach ($group in $groupList) {
        # This command sets a breakpoint on the Server variable in the Sample.ps1 script.
        $groupObj = Get-AzureADGroup -Filter "DisplayName eq '${group}'"
        # Write-Output "Group: -------------"
        # Write-Output $groupObj
        # Write-Output "*** ${groupObj.OjbectId}"
        # Start-Sleep -Seconds 10


        # This command sets a breakpoint on the Server variable in the Sample.ps1 script.
        # Write-Output "User: -------------"
        # Write-Output $user
        # Write-Output "*** ${user.OjbectId}"

        Write-Output "Adding $user.DisplayName to $groupObj.DisplayName"
        Add-AzureADGroupMember -ObjectId $groupObj.ObjectId -RefObjectId $user.ObjectId
    }
}
