<html xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xsl:version="1.0">
    <head>
        <title>Builds records table</title>
        <link rel="stylesheet" href="/templates/builds_records_table.css"/>
    </head>
    <body>
        <table>
            <thead>
                <tr>
                    <th>URL</th>
                    <th>Root Disk URL</th>
                    <th>Mediaserver Disk URL</th>
                </tr>
            </thead>
            <tbody>
                <xsl:variable name="url_separator" select="'/artifactory/'"/>
                <xsl:variable name="root_disk_separator" select="'/snapshots-origin'"/>
                <xsl:variable name="mediaserver_disk_separator" select="'/nxwitness-'"/>
                <xsl:for-each select="root/item">
                    <tr>
                        <td>
                            <xsl:variable name='url' select="url"/>
                                <xsl:choose>
                                    <xsl:when test="starts-with($url, 'https://artifactory.us.nxteam.dev/artifactory/')">
                                        <span class="small-text">
                                            <xsl:value-of select="substring-before($url, $url_separator)"/>
                                            <xsl:value-of select="$url_separator"/>
                                        </span>
                                        <xsl:value-of select="substring-after($url, $url_separator)"/>
                                    </xsl:when>
                                    <xsl:otherwise>
                                        <xsl:value-of select="$url"/>
                                    </xsl:otherwise>
                                </xsl:choose>
                        </td>
                        <td>
                            <xsl:variable name='root_disk_url' select="root_disk_url"/>
                            <xsl:choose>
                                <xsl:when test="contains($root_disk_url, $root_disk_separator)">
                                    <span class="small-text">
                                        <xsl:value-of select="substring-before($root_disk_url, $root_disk_separator)"/>
                                        <xsl:value-of select="$root_disk_separator"/>
                                    </span>
                                    <xsl:value-of select="substring-after($root_disk_url, $root_disk_separator)"/>
                                </xsl:when>
                                <xsl:otherwise>
                                    <xsl:value-of select="$root_disk_url"/>
                                </xsl:otherwise>
                            </xsl:choose>
                        </td>
                        <td>
                            <xsl:variable name='mediaserver_disk_url' select="mediaserver_disk_url"/>
                            <xsl:choose>
                                <xsl:when test="contains($mediaserver_disk_url, $mediaserver_disk_separator)">
                                    <span class="small-text">
                                        <xsl:value-of select="substring-before($mediaserver_disk_url, $mediaserver_disk_separator)"/>
                                        <xsl:value-of select="$mediaserver_disk_separator"/>
                                    </span>
                                    <xsl:value-of select="substring-after($mediaserver_disk_url, $mediaserver_disk_separator)"/>
                                </xsl:when>
                                <xsl:otherwise>
                                    <xsl:variable name="visible_num" select="30"/>
                                    <xsl:value-of select="substring($mediaserver_disk_url, 1, $visible_num)"/>
                                    <span class="small-text">
                                        <xsl:value-of select="substring($mediaserver_disk_url, $visible_num + 1)"/>
                                    </span>
                                </xsl:otherwise>
                            </xsl:choose>
                        </td>
                    </tr>
                </xsl:for-each>
            </tbody>
        </table>
    </body>
</html>