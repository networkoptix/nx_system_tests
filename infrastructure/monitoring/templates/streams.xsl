<html xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xsl:version="1.0">
    <head>
        <link rel="stylesheet" href="/templates/table.css"/>
        <link rel="stylesheet" href="/templates/streams.css"/>
    </head>
    <body>
        <h1><xsl:value-of select="root/app_name"/> streams:</h1>
        <table>
            <thead>
                <tr>
                    <th>Stream ID</th>
                    <th>Group Name</th>
                    <th>Lag</th>
                    <th>PEL Count</th>
                </tr>
            </thead>
            <tbody>
                <xsl:for-each select="root/groups/item">
                    <tr>
                        <td><xsl:value-of select="stream_id"/></td>
                        <td><a href="{group_href}"><xsl:value-of select="group_data/name"/></a></td>
                        <td class="digits"><xsl:value-of select="group_data/lag"/></td>
                        <td class="digits"><xsl:value-of select="group_data/pel_count"/></td>
                    </tr>
                </xsl:for-each>
            </tbody>
        </table>
    </body>
</html>

